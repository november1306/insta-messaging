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


@router.get(
    "/events",
    summary="Server-Sent Events stream for real-time updates",
    responses={
        200: {
            "description": "SSE stream established",
            "content": {
                "text/event-stream": {
                    "example": "data: {\"event\":\"connected\",\"message\":\"SSE stream connected\"}\\n\\n"
                }
            }
        }
    }
)
async def stream_events():
    """
    Server-Sent Events (SSE) endpoint for real-time message updates.

    Connect to this endpoint to receive live updates without polling:
    - `connected` - Initial connection confirmation
    - `new_message` - When Instagram message received via webhook
    - `message_status` - When message delivery status changes
    - `keepalive` - Every 30 seconds to prevent connection timeout

    ## Event Types

    ### `connected`
    Sent immediately upon connection:
    ```json
    {"event": "connected", "message": "SSE stream connected"}
    ```

    ### `new_message`
    Sent when new Instagram message arrives:
    ```json
    {
      "event": "new_message",
      "data": {
        "id": "mid_abc123",
        "sender_id": "25964748486442669",
        "sender_name": "@johndoe",
        "text": "Hello!",
        "direction": "inbound",
        "timestamp": "2026-01-06T14:32:00.123Z",
        "messaging_channel_id": "17841478096518771",
        "account_id": "acc_a3f7e8b2c1d4",
        "attachments": []
      },
      "timestamp": "2026-01-06T14:32:01.456Z"
    }
    ```

    ### `message_status`
    Sent when outbound message status changes:
    ```json
    {
      "event": "message_status",
      "data": {
        "message_id": "msg_a1b2c3d4e5f6",
        "status": "sent"
      },
      "timestamp": "2026-01-06T14:32:02.789Z"
    }
    ```

    ### `keepalive`
    Sent every 30 seconds to prevent timeout:
    ```
    : keepalive
    ```

    ## Client Implementation

    ### JavaScript (Browser)
    ```javascript
    const eventSource = new EventSource('/api/v1/events');

    eventSource.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);

      if (data.event === 'new_message') {
        console.log('New message:', data.data);
        // Update UI with new message
      }

      if (data.event === 'message_status') {
        console.log('Status update:', data.data);
        // Update message status in UI
      }
    });

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      eventSource.close();
    };
    ```

    ### Python
    ```python
    import requests
    import json

    response = requests.get(
        'https://api.example.com/api/v1/events',
        stream=True,
        headers={'Accept': 'text/event-stream'}
    )

    for line in response.iter_lines():
        if line.startswith(b'data:'):
            data = json.loads(line[5:])
            if data['event'] == 'new_message':
                print(f"New message: {data['data']['text']}")
    ```

    ## Connection Management

    - **Automatic Cleanup**: Stale connections removed after 5 minutes of inactivity
    - **Max Queue Size**: 100 messages per connection (older messages dropped if exceeded)
    - **Keepalive**: Every 30 seconds to prevent proxy/firewall timeouts
    - **Disconnection**: Gracefully handled on client close or error

    ## Production Considerations

    **For high-scale deployments**:
    - Current implementation uses in-memory SSE manager (not suitable for multiple servers)
    - **Recommended**: Replace with Redis pub/sub for horizontal scaling
    - **Limitation**: All SSE connections must go to same server instance

    **Alternatives to SSE**:
    - WebSocket (bidirectional, more complex)
    - Long polling (fallback for old browsers)
    - Firebase/Pusher (managed service)

    ## Browser Compatibility

    SSE is supported by:
    - ✅ Chrome 6+
    - ✅ Firefox 6+
    - ✅ Safari 5+
    - ✅ Edge 79+
    - ❌ Internet Explorer (use polyfill or long polling)
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


async def broadcast_message_status(
    message_id: str,
    status: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None
):
    """
    Broadcast a message status update to all connected SSE clients.
    Call this when message delivery status changes.

    Args:
        message_id: CRM outbound message ID
        status: Message status (pending, sent, failed)
        error_code: Error category (only for failed status)
        error_message: Human-readable error description (only for failed status)
    """
    data = {
        "message_id": message_id,
        "status": status
    }

    # Include error details for failed messages
    if status == "failed":
        if error_code:
            data["error_code"] = error_code
        if error_message:
            data["error_message"] = error_message

    await sse_manager.broadcast("message_status", data)
