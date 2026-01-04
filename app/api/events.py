"""
Server-Sent Events (SSE) endpoint for real-time message updates
Broadcasts new messages and status updates to connected frontend clients

PRODUCTION NOTE: For high-scale deployments, replace in-memory SSE manager
with Redis pub/sub to support multiple server instances and better reliability.
"""
import asyncio
import json
import logging
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class SSEConnection:
    """
    Represents an SSE connection with metadata for automatic cleanup.

    Tracks connection age and activity to prevent memory leaks from
    abandoned connections (browser close, network timeout, etc.)
    """
    queue: asyncio.Queue
    created_at: float
    last_activity: float

    def is_stale(self, timeout: int = 300) -> bool:
        """Check if connection is stale (no activity for timeout seconds)"""
        return (time.time() - self.last_activity) > timeout

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()


class SSEManager:
    """
    Manages Server-Sent Events connections with automatic cleanup.

    Features:
    - Tracks connection metadata (created_at, last_activity)
    - Automatic cleanup of stale connections every 60 seconds
    - Detects and removes failed connections during broadcast
    - Stops cleanup task when no connections active (resource efficient)

    Memory Safety:
    - Stale connections removed after 5 minutes of inactivity
    - Failed broadcasts immediately remove connection
    - Queue size limited to prevent memory growth
    """

    def __init__(self, stale_timeout: int = 300, max_queue_size: int = 100):
        self.active_connections: list[SSEConnection] = []
        self.stale_timeout = stale_timeout
        self.max_queue_size = max_queue_size
        self._cleanup_task: Optional[asyncio.Task] = None

    async def connect(self) -> SSEConnection:
        """Create a new SSE connection with automatic cleanup"""
        connection = SSEConnection(
            queue=asyncio.Queue(maxsize=self.max_queue_size),
            created_at=time.time(),
            last_activity=time.time()
        )
        self.active_connections.append(connection)
        logger.info(f"New SSE connection. Total connections: {len(self.active_connections)}")

        # Start cleanup task if not running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

        return connection

    def disconnect(self, connection: SSEConnection):
        """Remove an SSE connection"""
        if connection in self.active_connections:
            self.active_connections.remove(connection)
            logger.info(f"SSE connection closed. Total connections: {len(self.active_connections)}")

    async def _periodic_cleanup(self):
        """
        Periodically clean up stale connections.

        Runs every 60 seconds and removes connections with no activity
        for more than stale_timeout seconds. Stops when no connections remain.
        """
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                stale_connections = [
                    conn for conn in self.active_connections
                    if conn.is_stale(self.stale_timeout)
                ]

                for conn in stale_connections:
                    logger.warning(
                        f"Removing stale SSE connection (inactive for {self.stale_timeout}s). "
                        f"Connection age: {time.time() - conn.created_at:.0f}s"
                    )
                    self.disconnect(conn)

                # Stop cleanup task if no connections (saves resources)
                if not self.active_connections:
                    logger.info("No active SSE connections, stopping cleanup task")
                    break

            except Exception as e:
                logger.error(f"Error in SSE cleanup task: {e}")
                # Continue running despite errors

    async def broadcast(self, event: str, data: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.

        Automatically removes connections that fail to receive messages
        (queue full, closed connection, etc.)
        """
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Broadcasting SSE event '{event}' to {len(self.active_connections)} clients")

        # Track failed connections for cleanup
        failed_connections = []

        for connection in self.active_connections:
            try:
                # Use put_nowait to avoid blocking if queue is full
                # If queue is full, connection is not keeping up and should be dropped
                connection.queue.put_nowait(message)
                connection.update_activity()
            except asyncio.QueueFull:
                logger.warning(
                    f"SSE queue full (max={self.max_queue_size}), "
                    "client not consuming messages fast enough"
                )
                failed_connections.append(connection)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")
                failed_connections.append(connection)

        # Clean up failed connections immediately
        for conn in failed_connections:
            self.disconnect(conn)


# Global SSE manager instance
# - 300s (5 minute) stale timeout
# - 100 message queue size limit per connection
sse_manager = SSEManager(stale_timeout=300, max_queue_size=100)


@router.get("/events")
async def stream_events():
    """
    Server-Sent Events endpoint for real-time updates.

    Clients connect to this endpoint to receive:
    - new_message: When Instagram messages are received
    - message_status: When message delivery status changes
    - keepalive: Every 30 seconds to prevent connection timeout

    Connection Management:
    - Automatically cleaned up after 5 minutes of inactivity
    - Disconnected immediately on client close or error
    - Max 100 queued messages per connection
    """

    async def event_generator():
        """Generate SSE events for this client"""
        connection = await sse_manager.connect()

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event': 'connected', 'message': 'SSE stream connected'})}\n\n"

            # Keep-alive ping every 30 seconds
            ping_interval = 30
            last_ping = time.time()

            while True:
                try:
                    # Wait for message with timeout for keep-alive
                    message = await asyncio.wait_for(
                        connection.queue.get(),
                        timeout=ping_interval
                    )

                    # Send the message
                    yield f"data: {json.dumps(message)}\n\n"
                    connection.update_activity()
                    last_ping = time.time()

                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    current_time = time.time()
                    if current_time - last_ping >= ping_interval:
                        yield f": keepalive\n\n"
                        connection.update_activity()
                        last_ping = current_time

                except asyncio.CancelledError:
                    logger.info("SSE stream cancelled by client")
                    break

        except GeneratorExit:
            # Client closed connection
            logger.info("SSE client disconnected")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            # Always clean up connection
            sse_manager.disconnect(connection)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


async def broadcast_new_message(message: Dict[str, Any]):
    """
    Broadcast a new message to all connected SSE clients.
    Call this from webhook handler when a new Instagram message arrives.
    """
    await sse_manager.broadcast("new_message", message)


async def broadcast_message_status(message_id: str, status: str):
    """
    Broadcast a message status update to all connected SSE clients.
    Call this when message delivery status changes.
    """
    await sse_manager.broadcast("message_status", {
        "message_id": message_id,
        "status": status
    })
