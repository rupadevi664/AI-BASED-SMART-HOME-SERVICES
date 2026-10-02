"""Booking-scoped WebSocket connection manager (Phases 4 + 5).

Connections are grouped by booking id AND channel (`"chat"` or `"location"`)
so chat messages and live-location updates never mix, and so a payload only
ever reaches the participants of that booking. A user may hold several
simultaneous connections (browser + mobile); each is tracked independently
and removed safely on disconnect.
"""
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Supported channels — chat (Phase 4) and live location (Phase 5) are kept
# deliberately separate so neither traffic class reaches the other's sockets.
CHANNEL_CHAT = "chat"
CHANNEL_LOCATION = "location"
VALID_CHANNELS = {CHANNEL_CHAT, CHANNEL_LOCATION}


class ConnectionManager:
    def __init__(self) -> None:
        # (booking_id, channel) -> list of active sockets. Kept as one mapping
        # with a composite key so lookup/disconnect/broadcast logic is shared.
        self._connections: dict[tuple[int, str], list[WebSocket]] = defaultdict(list)

    def _key(self, booking_id: int, channel: str) -> tuple[int, str]:
        if channel not in VALID_CHANNELS:
            raise ValueError(f"Unknown channel: {channel!r}")
        return (booking_id, channel)

    async def connect(self, booking_id: int, websocket: WebSocket, channel: str = CHANNEL_CHAT) -> None:
        await websocket.accept()
        self._connections[self._key(booking_id, channel)].append(websocket)

    def disconnect(self, booking_id: int, websocket: WebSocket, channel: str = CHANNEL_CHAT) -> None:
        key = self._key(booking_id, channel)
        sockets = self._connections.get(key, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            # Drop empty rooms so the mapping does not grow unbounded.
            self._connections.pop(key, None)

    def get_booking_connections(self, booking_id: int, channel: str = CHANNEL_CHAT) -> list[WebSocket]:
        return list(self._connections.get(self._key(booking_id, channel), []))

    async def broadcast_to_booking(
        self, booking_id: int, payload: dict, channel: str = CHANNEL_CHAT
    ) -> None:
        """Send a JSON payload to every connection in the booking's channel."""
        for socket in self.get_booking_connections(booking_id, channel):
            try:
                await socket.send_json(payload)
            except Exception:
                logger.debug("Dropping dead socket in booking %s (%s)", booking_id, channel)
                self.disconnect(booking_id, socket, channel)


# Single shared instance for the application process.
manager = ConnectionManager()
