"""
WebSocket connection manager.
Connection'ları room bazlı yönetir.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.security import decode_token

logger = get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


# ── Connection Manager ────────────────────────────────────────────────────────


class ConnectionManager:
    """WebSocket connection yönetimi (room-based).

    Kullanıcıları room'lara alır, broadcast mesaj gönderimi sağlar.
    Bir kullanıcı birden fazla room'a bağlanabilir. Connection pool
    dictionary olarak saklanır (room_id -> user_id -> WebSocket).

    Attributes:
        _rooms: Room bazlı aktif bağlantılar.
            {room_id: {user_id: WebSocket}} yapısında dictionary.

    Example:
        >>> manager = ConnectionManager()
        >>> await manager.connect(websocket, room_id="lobby", user_id="user-uuid-123")
        >>> await manager.broadcast_to_room("lobby", {"event": "new_user"})
        >>> manager.disconnect(room_id="lobby", user_id="user-uuid-123")

    Note:
        - JWT token ile authentication (ilk mesaj olarak gönderilir)
        - Room oluşturma otomatik (ilk connect'te)
        - Graceful disconnect handling (exception safe)
    """

    def __init__(self) -> None:
        """ConnectionManager instance oluşturur.

        Boş room dictionary ile başlatır. Room'lar ilk bağlantıda
        otomatik olarak oluşturulur (defaultdict sayesinde).
        """
        # room_id → {user_id: WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str) -> None:
        """WebSocket bağlantısını room'a ekler.

        Endpoint tarafından accept() çağrıldıktan sonra bu metot
        bağlantıyı ilgili room'a kaydeder. Room yoksa otomatik oluşturulur.

        Args:
            websocket: FastAPI WebSocket instance (zaten accept() edilmiş).
            room_id: Bağlanılacak room ID'si (string).
            user_id: Kullanıcı ID'si (genellikle UUID string).

        Note:
            - websocket.accept() bu metot tarafından çağrılmaz.
            - Aynı user birden fazla room'da olabilir.
            - Room yoksa defaultdict otomatik oluşturur.
        """
        # Endpoint zaten accept() çağırdı — burada yalnızca kayıt yapılır
        self._rooms[room_id][user_id] = websocket
        logger.info("ws_connected", room_id=room_id, user_id=user_id)

    def disconnect(self, room_id: str, user_id: str) -> None:
        """Kullanıcıyı room'dan çıkarır ve bağlantıyı sonlandırır.

        Room'dan kullanıcıyı siler. Eğer room boşalırsa room'u da
        temizler (memory leak önleme).

        Args:
            room_id: Kullanıcının bulunduğu room ID'si.
            user_id: Çıkarılacak kullanıcı ID'si.

        Note:
            - Room veya user yoksa sessizce pass eder.
            - Room boşalırsa otomatik silinir.
            - WebSocket.close() çağrılmaz (caller sorumluluğu).
        """
        room = self._rooms.get(room_id, {})
        room.pop(user_id, None)
        if not room:
            self._rooms.pop(room_id, None)
        logger.info("ws_disconnected", room_id=room_id, user_id=user_id)

    async def send_to_user(self, user_id: str, room_id: str, message: dict[str, object]) -> None:
        """Belirli bir kullanıcıya özel mesaj gönderir (room içinde).

        Kullanıcıyı belirtilen room'da bulur ve JSON mesaj gönderir.
        Gönderim başarısız olursa kullanıcıyı otomatik disconnect eder.

        Args:
            user_id: Hedef kullanıcı ID'si.
            room_id: Kullanıcının bulunduğu room ID'si.
            message: JSON serialize edilebilir dictionary.

        Note:
            - Kullanıcı room'da değilse sessizce pass eder.
            - Gönderim hatası durumunda otomatik disconnect.
            - Exception raise etmez (graceful handling).
        """
        ws = self._rooms.get(room_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except RuntimeError:
                self.disconnect(room_id, user_id)

    async def broadcast_to_room(
        self, room_id: str, message: dict[str, object], exclude: str | None = None
    ) -> None:
        """Room'daki tüm kullanıcılara broadcast mesaj gönderir.

        Belirtilen room'daki tüm aktif bağlantılara aynı mesajı gönderir.
        İsteğe bağlı olarak bir kullanıcıyı exclude edebilir (örneğin
        mesajı gönderen kişi). Gönderim başarısız olan kullanıcıları
        otomatik disconnect eder.

        Args:
            room_id: Broadcast yapılacak room ID'si.
            message: Gönderilecek JSON dictionary.
            exclude: Mesaj gönderilmeyecek kullanıcı ID'si (opsiyonel).

        Note:
            - Room yoksa sessizce pass eder.
            - Gönderim hataları otomatik disconnect tetikler.
            - Exclude genellikle mesajı gönderen kullanıcıdır.

        Example:
            >>> await manager.broadcast_to_room(
            ...     "lobby",
            ...     {"type": "user_joined", "user_id": "alice"},
            ...     exclude="alice"  # Alice'e gönderme
            ... )
        """
        room = self._rooms.get(room_id, {})
        dead_users = []
        for user_id, ws in room.items():
            if user_id == exclude:
                continue
            try:
                await ws.send_json(message)
            except RuntimeError:
                dead_users.append(user_id)
        for user_id in dead_users:
            self.disconnect(room_id, user_id)

    def get_room_users(self, room_id: str) -> list[str]:
        """Room'daki aktif kullanıcı ID'lerini döndürür.

        Args:
            room_id: Sorgulanacak room ID'si.

        Returns:
            Kullanıcı ID'leri listesi (string). Room yoksa boş liste.

        Example:
            >>> users = manager.get_room_users("lobby")
            >>> print(users)  # ['user-1', 'user-2', 'user-3']
        """
        return list(self._rooms.get(room_id, {}).keys())

    async def send_to_user_all_rooms(self, user_id: str, message: dict[str, object]) -> None:
        """Kullanıcının bağlı olduğu tüm room'lara mesaj gönderir.

        Kullanıcının aktif olduğu her room'da aynı mesajı gönderir.
        Genellikle bildirim (notification) senaryolarında kullanılır.
        Gönderim başarısız olan room'lardan otomatik disconnect eder.

        Args:
            user_id: Hedef kullanıcı ID'si.
            message: Gönderilecek JSON dictionary.

        Note:
            - Kullanıcı hiçbir room'da yoksa sessizce pass eder.
            - list() ile snapshot alınır (iteration sırasında dict değişebilir).
            - Gönderim hatası otomatik disconnect tetikler.

        Example:
            >>> await manager.send_to_user_all_rooms(
            ...     "user-123",
            ...     {"type": "notification", "text": "Yeni mesajınız var"}
            ... )
        """
        for room_id, room in list(self._rooms.items()):
            if user_id in room:
                ws = room[user_id]
                try:
                    await ws.send_json(message)
                except RuntimeError:
                    self.disconnect(room_id, user_id)


# Singleton
manager = ConnectionManager()


# ── Endpoint ──────────────────────────────────────────────────────────────────

_WS_AUTH_TIMEOUT = 10.0  # saniye — ilk mesaj için bekleme süresi
_WS_MAX_MESSAGE_BYTES = 64 * 1024  # 64 KB — tek mesaj payload limiti
_WS_MAX_MESSAGE_LENGTH = 4096  # characters — max content length per message


def _decode_ws_message(message: dict[str, object]) -> dict[str, object] | None:
    """WebSocket frame'ini dict payload'a çevir."""
    if text := message.get("text"):
        if not isinstance(text, str):
            return None
        try:
            payload = json.loads(text)
        except ValueError:
            return None
        return cast(dict[str, object], payload) if isinstance(payload, dict) else None

    if raw_bytes := message.get("bytes"):
        if not isinstance(raw_bytes, bytes):
            return None
        if len(raw_bytes) > _WS_MAX_MESSAGE_BYTES:
            return {"type": "error", "reason": "Mesaj boyutu limiti aşıldı."}
        try:
            payload = json.loads(raw_bytes)
        except ValueError:
            return None
        return cast(dict[str, object], payload) if isinstance(payload, dict) else None

    return None


@router.websocket("/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
) -> None:
    """
    WebSocket bağlantısı.
    Bağlantı kurulunca ilk mesaj {"type": "auth", "token": "<access_token>"} olmalıdır.
    Token URL'de gönderilmez — server log'larına yazılmasını önler.

    Bağlantı: ws://localhost:8000/api/v1/shared/ws/{room_id}
    İlk mesaj: {"type": "auth", "token": "<access_token>"}
    """
    await websocket.accept()

    # İlk mesaj auth olmalı (timeout içinde)
    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=_WS_AUTH_TIMEOUT)
    except TimeoutError:
        await websocket.close(code=4008, reason="Auth timeout.")
        return
    except WebSocketDisconnect:
        return
    except (RuntimeError, ValueError, TypeError):
        await websocket.close(code=4001, reason="Geçersiz mesaj formatı.")
        return

    if raw.get("type") != "auth" or not raw.get("token"):
        await websocket.close(code=4001, reason="Auth mesajı gerekli: {type: 'auth', token: '...'}")
        return

    from app.core.exceptions import InvalidTokenError, TokenExpiredError

    try:
        payload = decode_token(raw["token"])
        user_id = payload.sub
    except TokenExpiredError:
        await websocket.close(code=4001, reason="Token süresi dolmuş.")
        return
    except (InvalidTokenError, ValueError, TypeError):
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
            frame = await websocket.receive()
            if frame["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(frame.get("code", 1000))

            data = _decode_ws_message(dict(frame))
            if data is None:
                await websocket.send_json({"type": "error", "reason": "Geçersiz JSON."})
                continue
            if data.get("type") == "error":
                await websocket.send_json(data)
                continue

            msg_type = data.get("type", "message")

            if msg_type == "message":
                content = str(data.get("content", ""))
                if len(content) > _WS_MAX_MESSAGE_LENGTH:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "reason": f"Mesaj içeriği {_WS_MAX_MESSAGE_LENGTH} karakteri aşamaz.",
                        }
                    )
                    continue
                await manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "message",
                        "from": user_id,
                        "content": content,
                        "room_id": room_id,
                    },
                    exclude=user_id,
                )
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(room_id, user_id)
        await manager.broadcast_to_room(
            room_id,
            {"type": "user_left", "user_id": user_id},
        )
    except RuntimeError:
        logger.exception("ws_unexpected_error", room_id=room_id, user_id=user_id)
        manager.disconnect(room_id, user_id)
