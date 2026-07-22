"""WebSocket manager – broadcasts simulation events to all connected clients."""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("ws_manager")


class WSManager:
    """Manages WebSocket connections and broadcasts simulation updates."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {
            "dashboard": set(),
        }
        self._latest_data: dict = {}

    async def connect(self, ws: WebSocket, channel: str = "dashboard"):
        """Accept a new WebSocket connection."""
        await ws.accept()
        self._connections.setdefault(channel, set()).add(ws)
        logger.info(f"WS connected ({channel}), total: {len(self._connections[channel])}")
        # Send current state immediately
        if self._latest_data:
            await self._send(ws, self._latest_data)

    def disconnect(self, ws: WebSocket, channel: str = "dashboard"):
        """Remove a disconnected client."""
        self._connections.get(channel, set()).discard(ws)

    async def broadcast(self, data: dict, channel: str = "dashboard"):
        """Push data to all connected clients on a channel."""
        self._latest_data = data
        dead = set()
        for ws in self._connections.get(channel, set()):
            try:
                await self._send(ws, data)
            except Exception:
                dead.add(ws)
        # Clean up dead connections
        self._connections[channel] -= dead

    async def _send(self, ws: WebSocket, data: dict):
        """Send JSON to a single client."""
        await ws.send_text(json.dumps(data, default=str))

    @property
    def connected_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


# Singleton
ws_manager = WSManager()
