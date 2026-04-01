"""
TOTP / 2FA endpoint'leri.

POST /auth/totp/setup    → QR kodu + secret döndür
POST /auth/totp/verify   → Kodu doğrula, 2FA'yı aktif et, backup kodları döndür
POST /auth/totp/disable  → 2FA'yı kapat
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.services.totp import TOTPService

router = APIRouter(prefix="/auth/totp", tags=["2FA / TOTP"])


def get_totp_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TOTPService:
    return TOTPService(db)


TOTPServiceDep = Annotated[TOTPService, Depends(get_totp_service)]


class TOTPSetupResponse(MessageResponse):
    secret: str
    qr_code: str
    provisioning_uri: str


class TOTPCodeRequest(BaseModel):
    code: str


class BackupCodesResponse(MessageResponse):
    backup_codes: list[str]


@router.post("/setup", response_model=TOTPSetupResponse, summary="2FA kurulumunu başlat")
async def setup_totp(current_user: CurrentUserDep, service: TOTPServiceDep) -> dict[str, str]:
    """
    Yeni TOTP secret üretir ve QR kodu döndürür.
    Authenticator uygulamasına eklendikten sonra /verify ile onaylanmalı.
    """
    result = await service.setup(current_user)
    return {
        "message": "QR kodu oluşturuldu. Authenticator uygulamanızla tarayın.",
        **result,
    }


@router.post(
    "/verify",
    response_model=BackupCodesResponse,
    summary="2FA kodunu doğrula ve aktif et",
)
async def verify_totp(
    data: TOTPCodeRequest,
    current_user: CurrentUserDep,
    service: TOTPServiceDep,
) -> dict[str, object]:
    """
    Authenticator uygulamasından alınan kodu doğrular ve 2FA'yı aktif eder.
    Backup kodları döndürür — bunları güvenli bir yerde saklayın, bir daha gösterilmez.
    """
    backup_codes = await service.verify_and_enable(current_user, data.code)
    return {
        "message": "2FA başarıyla aktif edildi.",
        "backup_codes": backup_codes,
    }


@router.post("/disable", response_model=MessageResponse, summary="2FA'yı kapat")
async def disable_totp(
    data: TOTPCodeRequest,
    current_user: CurrentUserDep,
    service: TOTPServiceDep,
) -> MessageResponse:
    """Mevcut TOTP kodunu doğrulayarak 2FA'yı devre dışı bırakır."""
    await service.disable(current_user, data.code)
    return MessageResponse(message="2FA başarıyla devre dışı bırakıldı.")


class BackupCodeCountResponse(BaseModel):
    count: int
    message: str


@router.get(
    "/backup-codes/count",
    response_model=BackupCodeCountResponse,
    summary="Kalan backup kod sayısı",
)
async def get_backup_code_count(
    current_user: CurrentUserDep,
    service: TOTPServiceDep,
) -> BackupCodeCountResponse:
    """Kullanılmamış backup kod sayısını döndürür."""
    count = await service.get_backup_code_count(current_user)
    return BackupCodeCountResponse(
        count=count,
        message=f"{count} adet kullanılmamış backup kodunuz var.",
    )


@router.post(
    "/backup-codes/regenerate",
    response_model=BackupCodesResponse,
    summary="Backup kodları yenile",
)
async def regenerate_backup_codes(
    data: TOTPCodeRequest,
    current_user: CurrentUserDep,
    service: TOTPServiceDep,
) -> dict[str, object]:
    """
    Geçerli TOTP kodunu doğrulayarak backup kodları yeniden üretir.
    Eski backup kodlar geçersiz olur — yeni kodları güvenli bir yerde saklayın.
    """
    new_codes = await service.regenerate_backup_codes(current_user, data.code)
    return {
        "message": "Backup kodlar yenilendi. Eski kodlar artık geçersiz.",
        "backup_codes": new_codes,
    }
