"""Health check unit ve endpoint testleri."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

from app.core.health import check_redis, check_storage


def _make_storage_mock(
    head_bucket_error: Exception | None = None,
) -> MagicMock:
    """
    aioboto3.Session mock'u oluşturur.
    check_storage() → aioboto3.Session().client("s3").__aenter__() → s3.head_bucket()
    """
    mock_s3 = AsyncMock()
    mock_s3.head_bucket = AsyncMock(side_effect=head_bucket_error)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_ctx)
    return mock_session


class TestCheckRedis:
    """TestCheckRedis test grubunu içerir."""

    async def test_returns_true_when_connected(self, fake_redis: object) -> None:
        """fake_redis autouse fixture aktifken check_redis() → (True, 'ok')."""
        ok, msg = await check_redis()
        assert ok is True
        assert msg == "ok"

    async def test_returns_false_on_connection_error(self) -> None:
        """Redis bağlantısı başarısız olursa → (False, hata_mesajı)."""
        with patch(
            "app.core.health.get_redis_client",
            side_effect=Exception("connection refused"),
        ):
            ok, msg = await check_redis()
        assert ok is False
        assert "connection refused" in msg


class TestCheckStorage:
    """TestCheckStorage test grubunu içerir."""

    async def test_returns_true_when_bucket_accessible(self) -> None:
        """S3 bucket erişilebilirken → (True, 'ok')."""
        mock_session = _make_storage_mock()
        with patch("app.core.health.aioboto3.Session", return_value=mock_session):
            ok, msg = await check_storage()
        assert ok is True
        assert msg == "ok"

    async def test_returns_false_when_bucket_missing(self) -> None:
        """Bucket bulunamazsa → (False, hata_mesajı)."""
        mock_session = _make_storage_mock(head_bucket_error=Exception("NoSuchBucket"))
        with patch("app.core.health.aioboto3.Session", return_value=mock_session):
            ok, msg = await check_storage()
        assert ok is False
        assert "NoSuchBucket" in msg


class TestHealthEndpoints:
    """TestHealthEndpoints test grubunu içerir."""

    async def test_health_ready_returns_503_when_redis_down(self, client: AsyncClient) -> None:
        """/health/ready Redis kapalıyken → 503 döndürmeli."""
        with patch(
            "app.core.health.get_redis_client",
            side_effect=Exception("redis down"),
        ):
            res = await client.get("/health/ready")
        assert res.status_code == 503
        # Exception handler {"error": {"code": ..., "message": ...}} formatında döner
        # message içinde "redis" kelimesi geçmeli
        assert "redis" in res.json()["error"]["message"].lower()

    async def test_health_returns_degraded_when_storage_down(self, client: AsyncClient) -> None:
        """/health storage kapalıyken → 200 degraded (storage opsiyonel)."""
        mock_session = _make_storage_mock(head_bucket_error=Exception("no bucket"))
        with patch("app.core.health.aioboto3.Session", return_value=mock_session):
            res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] in ("ok", "degraded")

    async def test_health_ready_returns_503_when_storage_down(self, client: AsyncClient) -> None:
        """/health/ready storage kapalıyken → 503 döndürmeli."""
        mock_session = _make_storage_mock(head_bucket_error=Exception("no bucket"))
        with patch("app.core.health.aioboto3.Session", return_value=mock_session):
            res = await client.get("/health/ready")
        assert res.status_code == 503
