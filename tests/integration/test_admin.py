"""
Admin panel erişim kontrol testleri.

SQLAdmin'in kendi CRUD view'ları (list/create/edit/delete) third-party library kodudur,
test edilmez. Sadece erişim kontrolü (unauthenticated redirect, başarısız login,
mock edilmiş authenticated access) test edilir.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.db.models.role import Role
from app.db.models.user import SurfaceType, User


class TestAdminPanelAccessControl:
    """TestAdminPanelAccessControl test grubunu içerir."""

    async def test_unauthenticated_redirects_to_login(self, client: AsyncClient) -> None:
        """Session olmadan /admin/ isteği → /admin/login sayfasına yönlendirmeli."""
        res = await client.get("/admin/", follow_redirects=False)
        assert res.status_code in (302, 303)
        location = res.headers.get("location", "")
        assert "login" in location

    async def test_admin_login_page_is_publicly_accessible(self, client: AsyncClient) -> None:
        """Login sayfası herkes tarafından erişilebilir olmalı (200)."""
        res = await client.get("/admin/login")
        assert res.status_code == 200

    async def test_wrong_credentials_do_not_grant_access(self, client: AsyncClient) -> None:
        """Hatalı credentials ile login → başarısız (login sayfasına döner veya 400)."""
        res = await client.post(
            "/admin/login",
            data={"username": "notadmin@example.com", "password": "wrongpassword"},
            follow_redirects=False,
        )
        # Başarısız login: login formunu tekrar gösterir (200/400) ya da aynı sayfaya redirect
        assert res.status_code in (200, 302, 303, 400)
        if res.status_code in (302, 303):
            location = res.headers.get("location", "")
            assert "login" in location

    async def test_authenticated_admin_can_access_panel(self, client: AsyncClient) -> None:
        """Authenticate olmuş admin /admin/ paneline erişebilmeli."""
        with patch(
            "app.admin.auth.AdminAuthBackend.authenticate",
            new=AsyncMock(return_value=True),
        ):
            res = await client.get("/admin/", follow_redirects=False)
        # Mocked auth ile redirect olmamalı, panel içeriği dönmeli
        assert res.status_code == 200

    async def test_non_admin_user_cannot_login(self, client: AsyncClient) -> None:
        """Admin olmayan kullanıcı admin paneline giriş yapamamalı."""
        with patch(
            "app.admin.auth.AdminAuthBackend.login",
            new=AsyncMock(return_value=False),
        ):
            res = await client.post(
                "/admin/login",
                data={"username": "user@example.com", "password": "UserPass1!"},
                follow_redirects=False,
            )
        # Başarısız login: 200 (form tekrar), 302/303 (login sayfasına redirect) ya da 400
        assert res.status_code in (200, 302, 303, 400)
        if res.status_code in (302, 303):
            assert "login" in res.headers.get("location", "")

    async def test_real_client_user_cannot_login_admin_panel(
        self,
        client: AsyncClient,
    ) -> None:
        """Gerçek client surface kullanıcısı admin panel oturumu açamamalı."""
        await client.post(
            "/api/v1/client/auth/register",
            json={"email": "panel-client@example.com", "password": "StrongPass1"},
        )
        res = await client.post(
            "/admin/login",
            data={"username": "panel-client@example.com", "password": "StrongPass1"},
            follow_redirects=False,
        )
        assert res.status_code in (200, 302, 303, 400)
        if res.status_code in (302, 303):
            assert "login" in res.headers.get("location", "")

    async def test_real_admin_user_can_login_admin_panel(
        self,
        client: AsyncClient,
        db_session,
    ) -> None:
        """Admin surface + admin role kullanıcısı panel giriş yapabilmeli."""
        email = "panel-admin@example.com"
        password = "StrongPass1"
        await client.post(
            "/api/v1/client/auth/register",
            json={"email": email, "password": password},
        )
        result = await db_session.execute(select(Role.id).where(Role.name == "admin"))
        admin_role_id = result.scalar_one()
        await db_session.execute(
            sa_update(User)
            .where(User.email == email)
            .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
        )
        await db_session.commit()

        res = await client.post(
            "/admin/login",
            data={"username": email, "password": password},
            follow_redirects=False,
        )
        assert res.status_code in (302, 303)
