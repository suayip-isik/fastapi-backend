"""
WebSocket connection manager.
Connection'ları room bazlı yönetir.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.security import decode_token

logger = get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


# ── Connection Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    """
    WebSocket bağlantı yöneticisi.
    - Room bazlı broadcast
    - Kullanıcı bazlı mesajlaşma
    """

    def __init__(self) -> None:
        # room_id → {user_id: WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str) -> None:
        await websocket.accept()
        self._rooms[room_id][user_id] = websocket
        logger.info("ws_connected", room_id=room_id, user_id=user_id)

    def disconnect(self, room_id: str, user_id: str) -> None:
        room = self._rooms.get(room_id, {})
        room.pop(user_id, None)
        if not room:
            self._rooms.pop(room_id, None)
        logger.info("ws_disconnected", room_id=room_id, user_id=user_id)

    async def send_to_user(self, user_id: str, room_id: str, message: dict) -> None:
        ws = self._rooms.get(room_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(room_id, user_id)

    async def broadcast_to_room(self, room_id: str, message: dict, exclude: str | None = None) -> None:
        room = self._rooms.get(room_id, {})
        dead_users = []
        for user_id, ws in room.items():
            if user_id == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead_users.append(user_id)
        for user_id in dead_users:
            self.disconnect(room_id, user_id)

    def get_room_users(self, room_id: str) -> list[str]:
        return list(self._rooms.get(room_id, {}).keys())


# Singleton
manager = ConnectionManager()


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.websocket("/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str,  # Query param: ws://host/ws/room?token=xxx
) -> None:
    """
    WebSocket bağlantısı.
    Token query param ile kimlik doğrulama yapılır.

    Bağlantı: ws://localhost:8000/api/v1/ws/{room_id}?token={access_token}
    """
    # Token doğrulama
    try:
        payload = decode_token(token)
        user_id = payload.sub
    except Exception:
        await websocket.close(code=4001, reason="Geçersiz token.")
        return

    await manager.connect(websocket, room_id, user_id)

    # Odaya katılım bildirimi
    await manager.broadcast_to_room(
        room_id,
        {"type": "user_joined", "user_id": user_id},
        exclude=user_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                await manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "message",
                        "from": user_id,
                        "content": data.get("content", ""),
                        "room_id": room_id,
                    },
                )
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(room_id, user_id)
        await manager.broadcast_to_room(
            room_id,
            {"type": "user_left", "user_id": user_id},
        )
