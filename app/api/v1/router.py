"""API v1 router — surface bazlı endpoint kompozisyonu."""

from fastapi import APIRouter

from app.api.v1.audiences import ADMIN, SHARED, tag_router
from app.api.v1.endpoints.api_keys import router as api_keys_router
from app.api.v1.endpoints.audit_logs import router as audit_logs_router
from app.api.v1.endpoints.auth import admin_router as admin_auth_router
from app.api.v1.endpoints.auth import client_router as client_auth_router
from app.api.v1.endpoints.auth import shared_router as shared_auth_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.roles import router as roles_router
from app.api.v1.endpoints.totp import router as totp_router
from app.api.v1.endpoints.uploads import router as uploads_router
from app.api.v1.endpoints.users import admin_router as admin_users_router
from app.api.v1.endpoints.users import shared_router as shared_users_router
from app.websockets.manager import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(client_auth_router)
api_router.include_router(tag_router(admin_auth_router, ADMIN))
api_router.include_router(shared_auth_router)

api_router.include_router(shared_users_router)
api_router.include_router(tag_router(admin_users_router, ADMIN))

api_router.include_router(tag_router(totp_router, SHARED), prefix="/shared")
api_router.include_router(tag_router(api_keys_router, SHARED), prefix="/shared")
api_router.include_router(tag_router(notifications_router, SHARED), prefix="/shared")
api_router.include_router(tag_router(uploads_router, SHARED), prefix="/shared")
api_router.include_router(tag_router(ws_router, SHARED), prefix="/shared")

api_router.include_router(tag_router(audit_logs_router, ADMIN), prefix="/admin")
api_router.include_router(tag_router(roles_router, ADMIN), prefix="/admin")

# Yeni modüller buraya eklenir:
# from app.api.v1.endpoints.posts import router as posts_router
# api_router.include_router(posts_router)
