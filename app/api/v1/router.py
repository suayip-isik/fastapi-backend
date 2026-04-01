"""API v1 router — tüm endpoint'leri toplar."""

from fastapi import APIRouter

from app.api.v1.audiences import ADMIN, USER, USER_AND_MOBILE, tag_router
from app.api.v1.endpoints.api_keys import router as api_keys_router
from app.api.v1.endpoints.audit_logs import router as audit_logs_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.totp import router as totp_router
from app.api.v1.endpoints.uploads import router as uploads_router
from app.api.v1.endpoints.users import router as users_router
from app.websockets.manager import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(tag_router(auth_router, USER_AND_MOBILE))
api_router.include_router(tag_router(totp_router, USER_AND_MOBILE))
api_router.include_router(tag_router(api_keys_router, USER))
api_router.include_router(tag_router(audit_logs_router, ADMIN))
api_router.include_router(tag_router(notifications_router, USER_AND_MOBILE))
api_router.include_router(tag_router(users_router, ADMIN))
api_router.include_router(tag_router(uploads_router, USER_AND_MOBILE))
api_router.include_router(tag_router(ws_router, USER_AND_MOBILE))

# Yeni modüller buraya eklenir:
# from app.api.v1.endpoints.posts import router as posts_router
# api_router.include_router(posts_router)
