"""
WebSocket endpoint testleri — /api/v1/ws/{room_id}

Bağlantı protokolü:
  1. Client bağlanır (accept)
  2. İlk mesaj: {"type": "auth", "token": "<access_token>"}
  3. Geçerli token → bağlantı kurulur
  4. Geçersiz/eksik → close(4001), timeout → close(4008)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────────

WS_URL = "/api/v1/ws/test-room"


@pytest.fixture(autouse=True)
def _patch_lifespan():
    """
    TestClient'ın kendi event loop'u pytest-asyncio'nun function-scoped loop'larıyla
    çakışır. Bu iki lifespan yan etkisini devre dışı bırakır:
    - close_redis(): FakeRedis.aclose() yok → AttributeError
    - create_default_admin(): asyncpg havuzunu kapalı loop'ta kullanır → RuntimeError
    """
    with (
        patch("app.main.close_redis", new=AsyncMock()),
        patch("app.main.create_default_admin", new=AsyncMock()),
        patch("app.main.seed_system_roles", new=AsyncMock()),
    ):
        yield


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ws_close_code(message: dict) -> int:
    """WebSocket'e mesaj gönder, sunucunun kapama kodunu döndür."""
    code = 0
    with TestClient(app) as client:
        try:
            with client.websocket_connect(WS_URL) as ws:
                ws.send_json(message)
                ws.receive_json()  # Sunucu close frame gönderdi, burası raise eder
        except WebSocketDisconnect as exc:
            code = exc.code
    return code


# ── Auth Hata Senaryoları ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_wrong_auth_message_type():
    """type='auth' olmayan ilk mesaj → 4001 ile kapatılmalı."""
    code = _ws_close_code({"type": "message", "content": "hello"})
    assert code == 4001


@pytest.mark.asyncio
async def test_ws_auth_message_missing_token():
    """type='auth' fakat token alanı yok → 4001 ile kapatılmalı."""
    code = _ws_close_code({"type": "auth"})
    assert code == 4001


@pytest.mark.asyncio
async def test_ws_auth_message_empty_token():
    """token değeri boş string → 4001 ile kapatılmalı."""
    code = _ws_close_code({"type": "auth", "token": ""})
    assert code == 4001


@pytest.mark.asyncio
async def test_ws_invalid_jwt_token():
    """Geçersiz JWT string → 4001 ile kapatılmalı."""
    code = _ws_close_code({"type": "auth", "token": "not.a.valid.jwt"})
    assert code == 4001


# ── Başarılı Bağlantı Senaryoları ─────────────────────────────────────────────
# NOT: Bu testler pytest-asyncio'nun async event loop'u ile Starlette TestClient'ın
# anyio kullanımı arasındaki çakışma nedeniyle askıda kalır.
# Çözüm: pytest-asyncio olmayan ayrı bir sync test süreci ile çalıştırılmalı.
# Örnek: pytest tests/integration/test_websocket.py -p no:asyncio -k "valid_auth or ping_pong or broadcast or echoed"


@pytest.mark.skip(
    reason="TestClient+asyncio event loop çakışması: ayrı sync test süreci gerektirir"
)
@pytest.mark.asyncio
async def test_ws_valid_auth_connects_successfully():
    """Geçerli access token ile bağlantı kurulmalı (ping → pong)."""
    token = create_access_token(str(uuid4()))
    with TestClient(app) as client, client.websocket_connect(WS_URL) as ws:
        ws.send_json({"type": "auth", "token": token})
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp == {"type": "pong"}


@pytest.mark.skip(
    reason="TestClient+asyncio event loop çakışması: ayrı sync test süreci gerektirir"
)
@pytest.mark.asyncio
async def test_ws_ping_pong_multiple_times():
    """Bağlantı aktif kaldığı sürece birden fazla ping/pong çalışmalı."""
    token = create_access_token(str(uuid4()))
    with TestClient(app) as client, client.websocket_connect(WS_URL) as ws:
        ws.send_json({"type": "auth", "token": token})
        for _ in range(3):
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            assert resp["type"] == "pong"


@pytest.mark.skip(
    reason="TestClient+asyncio event loop çakışması: ayrı sync test süreci gerektirir"
)
@pytest.mark.asyncio
async def test_ws_broadcast_message_to_room():
    """İki kullanıcı aynı odada: biri mesaj gönderince diğeri almalı."""
    token_a = create_access_token(str(uuid4()))
    token_b = create_access_token(str(uuid4()))
    with TestClient(app) as client, client.websocket_connect(WS_URL) as ws_a:
        ws_a.send_json({"type": "auth", "token": token_a})
        with client.websocket_connect(WS_URL) as ws_b:
            ws_b.send_json({"type": "auth", "token": token_b})
            joined = ws_a.receive_json()
            assert joined["type"] == "user_joined"
            ws_b.send_json({"type": "message", "content": "merhaba"})
            msg = ws_a.receive_json()
            assert msg["type"] == "message"
            assert msg["content"] == "merhaba"
            assert msg["room_id"] == "test-room"


@pytest.mark.skip(
    reason="TestClient+asyncio event loop çakışması: ayrı sync test süreci gerektirir"
)
@pytest.mark.asyncio
async def test_ws_message_not_echoed_to_sender():
    """Gönderilen mesaj gönderen kullanıcıya echo edilmemeli."""
    token_a = create_access_token(str(uuid4()))
    token_b = create_access_token(str(uuid4()))
    room = f"echo-test-{str(uuid4())[:8]}"
    with TestClient(app) as client, client.websocket_connect(f"/api/v1/ws/{room}") as ws_a:
        ws_a.send_json({"type": "auth", "token": token_a})
        with client.websocket_connect(f"/api/v1/ws/{room}") as ws_b:
            ws_b.send_json({"type": "auth", "token": token_b})
            ws_a.receive_json()  # user_joined tüket
            ws_b.send_json({"type": "message", "content": "no-echo"})
            msg = ws_a.receive_json()
            assert msg["type"] == "message"
            assert msg["content"] == "no-echo"
            ws_b.send_json({"type": "ping"})
            pong = ws_b.receive_json()
            assert pong["type"] == "pong"
