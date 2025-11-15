"""
Server-Sent Events (SSE) endpoint for real-time message updates
Broadcasts new messages and status updates to connected frontend clients
"""
import asyncio
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

# Global message queue for SSE broadcasts
# In production, use Redis pub/sub or similar
message_queue: asyncio.Queue = asyncio.Queue()


class SSEManager:
    """Manages Server-Sent Events connections"""

    def __init__(self):
        self.active_connections: list[asyncio.Queue] = []

    async def connect(self) -> asyncio.Queue:
        """Create a new SSE connection"""
        queue = asyncio.Queue()
        self.active_connections.append(queue)
        logger.info(f"New SSE connection. Total connections: {len(self.active_connections)}")
        return queue

    def disconnect(self, queue: asyncio.Queue):
        """Remove an SSE connection"""
        if queue in self.active_connections:
            self.active_connections.remove(queue)
            logger.info(f"SSE connection closed. Total connections: {len(self.active_connections)}")

    async def broadcast(self, event: str, data: Dict[str, Any]):
        """Broadcast a message to all connected clients"""
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"Broadcasting SSE event '{event}' to {len(self.active_connections)} clients")

        # Add to all client queues
        for queue in self.active_connections:
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client: {e}")


# Global SSE manager instance
sse_manager = SSEManager()


@router.get("/events")
async def stream_events():
    """
    Server-Sent Events endpoint for real-time updates.
    Clients connect to this endpoint to receive:
    - new_message: When Instagram messages are received
    - message_status: When message delivery status changes
    """

    async def event_generator():
        """Generate SSE events for this client"""
        queue = await sse_manager.connect()

        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event': 'connected', 'message': 'SSE stream connected'})}\n\n"

            # Keep-alive ping every 30 seconds
            ping_interval = 30
            last_ping = asyncio.get_event_loop().time()

            while True:
                try:
                    # Wait for message with timeout for keep-alive
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=ping_interval
                    )

                    # Send the message
                    yield f"data: {json.dumps(message)}\n\n"
                    last_ping = asyncio.get_event_loop().time()

                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_ping >= ping_interval:
                        yield f": keepalive\n\n"
                        last_ping = current_time

                except asyncio.CancelledError:
                    logger.info("SSE stream cancelled")
                    break

        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            sse_manager.disconnect(queue)

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
