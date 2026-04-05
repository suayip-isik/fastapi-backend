"""API v1 router — tüm endpoint'leri toplar."""

from fastapi import APIRouter

from app.api.v1.audiences import ADMIN, ALL, tag_router
from app.api.v1.endpoints.api_keys import router as api_keys_router
from app.api.v1.endpoints.audit_logs import router as audit_logs_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.roles import router as roles_router
from app.api.v1.endpoints.totp import router as totp_router
from app.api.v1.endpoints.uploads import router as uploads_router
from app.api.v1.endpoints.users import router as users_router
from app.websockets.manager import router as ws_router

ADMIN_AND_USER = ["admin", "user"]

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(tag_router(auth_router, ALL))
api_router.include_router(tag_router(totp_router, ALL))
api_router.include_router(tag_router(api_keys_router, ADMIN_AND_USER))
api_router.include_router(tag_router(audit_logs_router, ADMIN))
api_router.include_router(tag_router(notifications_router, ALL))
api_router.include_router(tag_router(users_router, ADMIN))
api_router.include_router(tag_router(roles_router, ADMIN))
api_router.include_router(tag_router(uploads_router, ALL))
api_router.include_router(tag_router(ws_router, ALL))

# Yeni modüller buraya eklenir:
# from app.api.v1.endpoints.posts import router as posts_router
# api_router.include_router(posts_router)
