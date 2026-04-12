"""
API Key endpoint'leri.

POST   /api-keys         → Yeni key oluştur
GET    /api-keys         → Kendi key'lerini listele
DELETE /api-keys/{id}   → Key iptal et
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    CurrentAuthDep,
    CurrentUserDep,
    get_effective_permissions,
    require_permissions,
)
from app.api.dependencies.infrastructure import PermissionProviderDep
from app.api.dependencies.services import AuditServiceDep
from app.core.config import settings
from app.core.i18n import t
from app.core.limiter import limiter
from app.core.permissions import Permission
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.services.api_key import APIKeyService

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

_APIKeysListDep = Annotated[object, Depends(require_permissions(Permission.API_KEYS_LIST))]
_APIKeysCreateDep = Annotated[object, Depends(require_permissions(Permission.API_KEYS_CREATE))]
_APIKeysRevokeDep = Annotated[object, Depends(require_permissions(Permission.API_KEYS_REVOKE))]


def get_api_key_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> APIKeyService:
    """APIKeyService dependency factory'si."""
    return APIKeyService(db, audit=audit)


APIKeyServiceDep = Annotated[APIKeyService, Depends(get_api_key_service)]


# ── Schemas ───────────────────────────────────────────────────────────────────


class CreateAPIKeyRequest(BaseModel):
    """API key oluşturma istek şeması."""

    name: str = Field(min_length=1, max_length=100)
    scopes: list[Permission] = Field(default_factory=list)
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        """İsim alanındaki baştaki ve sondaki boşlukları temizler."""
        v = v.strip()
        if not v:
            raise ValueError("İsim sadece boşluktan oluşamaz.")
        return v

    @field_validator("scopes")
    @classmethod
    def _normalize_scopes(cls, scopes: list[Permission]) -> list[Permission]:
        """Duplicate scope'ları kaldır ve deterministic sırala."""
        return sorted(set(scopes), key=lambda scope: scope.value)


class APIKeyCreatedResponse(BaseModel):
    """API key oluşturma yanıt şeması — ham key sadece bir kez gösterilir."""

    id: UUID
    key: str  # Ham key — sadece bir kez gösterilir
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    message: str = ""

    @classmethod
    def from_api_key(cls, raw_key: str, api_key: object) -> "APIKeyCreatedResponse":
        """APIKey model'inden response şeması oluşturur."""
        scopes_str: str = getattr(api_key, "scopes", "") or ""
        return cls(
            id=api_key.id,  # type: ignore[attr-defined]
            key=raw_key,
            name=api_key.name,  # type: ignore[attr-defined]
            key_prefix=api_key.key_prefix,  # type: ignore[attr-defined]
            scopes=scopes_str.split() if scopes_str else [],
            expires_at=api_key.expires_at,  # type: ignore[attr-defined]
            created_at=api_key.created_at,  # type: ignore[attr-defined]
            message=t("api_key.create.message"),
        )


class APIKeyResponse(BaseModel):
    """API key listeleme yanıt şeması — ham key değeri içermez."""

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: object, **kwargs: object) -> "APIKeyResponse":
        """APIKey model'inden response şeması oluşturur."""
        scopes_str: str = getattr(obj, "scopes", "") or ""
        return cls(
            id=obj.id,  # type: ignore[attr-defined]
            name=obj.name,  # type: ignore[attr-defined]
            key_prefix=obj.key_prefix,  # type: ignore[attr-defined]
            scopes=scopes_str.split() if scopes_str else [],
            last_used_at=obj.last_used_at,  # type: ignore[attr-defined]
            expires_at=obj.expires_at,  # type: ignore[attr-defined]
            is_active=obj.is_active,  # type: ignore[attr-defined]
            created_at=obj.created_at,  # type: ignore[attr-defined]
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "", response_model=APIKeyCreatedResponse, status_code=201, summary="Yeni API key oluştur"
)
@limiter.limit(settings.RATE_LIMIT_API_KEYS)
async def create_api_key(
    request: Request,
    data: CreateAPIKeyRequest,
    _: _APIKeysCreateDep,
    current_auth: CurrentAuthDep,
    permission_provider: PermissionProviderDep,
    service: APIKeyServiceDep,
) -> APIKeyCreatedResponse:
    """Yeni API key oluşturur.

    Kullanıcı için benzersiz bir API key oluşturur. Ham key değeri
    yalnızca bu yanıtta döner ve bir daha görüntülenemez.

    İstenen scope'lar kullanıcının sahip olduğu izinlerle kesiştirilir;
    kullanıcının yetkisi olmayan scope'lar sessizce filtrelenir.

    Args:
        data: API key oluşturma bilgileri (isim, scope'lar, son kullanma tarihi).
        current_auth: Kimliği doğrulanmış auth context.
        permission_provider: Permission çözümleme servisi.
        service: API key iş mantığı servisi.

    Returns:
        Oluşturulan API key bilgileri ve ham key değeri.

    Raises:
        HTTPException: Kullanıcı kimliği doğrulanamamışsa (401).
    """
    effective_perms = await get_effective_permissions(current_auth, permission_provider)
    requested_scopes = [scope.value for scope in data.scopes]
    allowed_scopes = [s for s in requested_scopes if s in effective_perms]

    raw_key, api_key = await service.create(
        user_id=current_auth.user.id,
        name=data.name,
        scopes=allowed_scopes,
        expires_at=data.expires_at,
    )
    return APIKeyCreatedResponse.from_api_key(raw_key, api_key)


@router.get("", response_model=list[APIKeyResponse], summary="API key'lerini listele")
async def list_api_keys(
    _: _APIKeysListDep,
    current_user: CurrentUserDep,
    service: APIKeyServiceDep,
) -> list[APIKeyResponse]:
    """Kullanıcının API key'lerini listeler.

    Mevcut kullanıcıya ait tüm aktif API key'leri döndürür.
    Güvenlik nedeniyle ham key değerleri gösterilmez, yalnızca
    key prefix'i ve meta bilgiler listelenir.

    Args:
        current_user: Kimliği doğrulanmış aktif kullanıcı.
        service: API key iş mantığı servisi.

    Returns:
        Kullanıcının aktif API key'lerinin listesi.

    Raises:
        HTTPException: Kullanıcı kimliği doğrulanamamışsa (401).
    """
    keys = await service.list_for_user(current_user.id)
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/{key_id}", response_model=MessageResponse, summary="API key iptal et")
@limiter.limit(settings.RATE_LIMIT_API_KEYS)
async def revoke_api_key(
    request: Request,
    key_id: UUID,
    _: _APIKeysRevokeDep,
    current_user: CurrentUserDep,
    service: APIKeyServiceDep,
) -> MessageResponse:
    """Belirtilen API key'i iptal eder.

    Kullanıcıya ait bir API key'i kalıcı olarak devre dışı bırakır.
    İptal edilen key ile artık kimlik doğrulaması yapılamaz.

    Args:
        key_id: İptal edilecek API key'in UUID'si.
        current_user: Kimliği doğrulanmış aktif kullanıcı.
        service: API key iş mantığı servisi.

    Returns:
        İşlem başarı mesajı.

    Raises:
        HTTPException: Key bulunamazsa veya kullanıcıya ait değilse (404).
    """
    await service.revoke(key_id, current_user.id)
    return MessageResponse(message=t("api_key.revoke.success"))
