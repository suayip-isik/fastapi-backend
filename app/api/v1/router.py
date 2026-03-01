"""API v1 router — tüm endpoint'leri toplar."""
from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.websockets.manager import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(ws_router)

# Yeni modüller buraya eklenir:
# from app.api.v1.endpoints.users import router as users_router
# api_router.include_router(users_router)
