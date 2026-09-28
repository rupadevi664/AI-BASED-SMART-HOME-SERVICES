"""Booking-scoped WebSocket connection manager (Phase 4).

Connections are grouped by booking id so messages only ever reach the
participants of that booking. A user may hold several simultaneous
connections (browser + mobile); each is tracked independently and removed
safely on disconnect.
"""
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # booking_id -> list of active sockets (both participants, any count).
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, booking_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[booking_id].append(websocket)

    def disconnect(self, booking_id: int, websocket: WebSocket) -> None:
        sockets = self._connections.get(booking_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            # Drop empty rooms so the mapping does not grow unbounded.
            self._connections.pop(booking_id, None)

    def get_booking_connections(self, booking_id: int) -> list[WebSocket]:
        return list(self._connections.get(booking_id, []))

    async def broadcast_to_booking(self, booking_id: int, payload: dict) -> None:
        """Send a JSON payload to every connection in the booking room."""
        for socket in self.get_booking_connections(booking_id):
            try:
                await socket.send_json(payload)
            except Exception:
                logger.debug("Dropping dead socket in booking %s", booking_id)
                self.disconnect(booking_id, socket)


# Single shared instance for the application process.
manager = ConnectionManager()
