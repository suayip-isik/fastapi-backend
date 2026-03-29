"""
API Key endpoint'leri.

POST   /api-keys         → Yeni key oluştur
GET    /api-keys         → Kendi key'lerini listele
DELETE /api-keys/{id}   → Key iptal et
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.services.api_key import APIKeyService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def get_api_key_service(db: Annotated[AsyncSession, Depends(get_db)]) -> APIKeyService:
    return APIKeyService(db)


APIKeyServiceDep = Annotated[APIKeyService, Depends(get_api_key_service)]


# ── Schemas ───────────────────────────────────────────────────────────────────


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class APIKeyCreatedResponse(BaseModel):
    id: UUID
    key: str  # Ham key — sadece bir kez gösterilir
    name: str
    key_prefix: str
    scopes: str
    expires_at: datetime | None
    created_at: datetime
    message: str = "API key oluşturuldu. Bu değeri güvenli bir yerde saklayın — bir daha gösterilmez."


class APIKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: str
    last_used_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", response_model=APIKeyCreatedResponse, status_code=201)
async def create_api_key(
    data: CreateAPIKeyRequest,
    current_user: CurrentUserDep,
    service: APIKeyServiceDep,
) -> APIKeyCreatedResponse:
    """Yeni API key oluştur. Ham key sadece bu yanıtta döner."""
    raw_key, api_key = await service.create(
        user_id=current_user.id,
        name=data.name,
        scopes=data.scopes,
        expires_at=data.expires_at,
    )
    return APIKeyCreatedResponse(
        id=api_key.id,
        key=raw_key,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: CurrentUserDep,
    service: APIKeyServiceDep,
) -> list[APIKeyResponse]:
    """Aktif API key'leri listele."""
    keys = await service.list_for_user(current_user.id)
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: UUID,
    current_user: CurrentUserDep,
    service: APIKeyServiceDep,
) -> MessageResponse:
    """API key'i iptal et."""
    await service.revoke(key_id, current_user.id)
    return MessageResponse(message="API key iptal edildi.")
