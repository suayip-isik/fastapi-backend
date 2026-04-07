"""
TOTP / 2FA endpoint'leri.

POST /auth/totp/setup    → QR kodu + secret döndür
POST /auth/totp/verify   → Kodu doğrula, 2FA'yı aktif et, backup kodları döndür
POST /auth/totp/disable  → 2FA'yı kapat
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep
from app.api.dependencies.services import AuditServiceDep
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.services.totp import TOTPService

router = APIRouter(prefix="/auth/totp", tags=["2FA / TOTP"])


def get_totp_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> TOTPService:
    """TOTPService dependency factory'si."""
    return TOTPService(db, audit=audit)


TOTPServiceDep = Annotated[TOTPService, Depends(get_totp_service)]


class TOTPSetupResponse(MessageResponse):
    """TOTP setup yanit modeli."""

    secret: str
    qr_code: str
    provisioning_uri: str


class TOTPCodeRequest(BaseModel):
    """TOTP kodu tasiyan istek modeli."""

    code: str = Field(..., pattern=r"^\d{6}$", description="6 haneli TOTP kodu")


class BackupCodesResponse(MessageResponse):
    """Backup kodlari liste yanit modeli."""

    backup_codes: list[str]


@router.post("/setup", response_model=TOTPSetupResponse, summary="2FA kurulumunu başlat")
async def setup_totp(current_user: CurrentUserDep, service: TOTPServiceDep) -> dict[str, str]:
    """TOTP kurulumunu başlatır ve QR kodu döndürür.

    Kullanıcı için yeni bir TOTP secret üretir. Döndürülen QR kodu
    authenticator uygulamasına (Google Authenticator, Authy vb.) eklenmeli
    ve ardından /verify endpoint'i ile doğrulanmalıdır.

    Args:
        current_user: Oturum açmış kullanıcı.
        service: TOTP işlemleri servisi.

    Returns:
        Secret, QR kodu (base64) ve provisioning URI içeren yanıt.

    Raises:
        HTTPException: 2FA zaten aktifse 400 hatası.
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
    """TOTP kodunu doğrular ve 2FA'yı aktif eder.

    Authenticator uygulamasından alınan 6 haneli kodu doğrular.
    Başarılı doğrulama sonrası 2FA kalıcı olarak aktif edilir ve
    tek kullanımlık backup kodları oluşturulur.

    Args:
        data: Doğrulanacak TOTP kodunu içeren istek.
        current_user: Oturum açmış kullanıcı.
        service: TOTP işlemleri servisi.

    Returns:
        Başarı mesajı ve backup kodları listesi.
        Backup kodları güvenli bir yerde saklanmalıdır.

    Raises:
        HTTPException: Kod geçersizse veya 2FA kurulmamışsa 400 hatası.
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
    """TOTP 2FA'yı devre dışı bırakır.

    Mevcut TOTP kodunu doğrulayarak hesaptaki iki faktörlü
    kimlik doğrulamayı kapatır. Tüm backup kodları da geçersiz olur.

    Args:
        data: Doğrulanacak TOTP kodunu içeren istek.
        current_user: Oturum açmış kullanıcı.
        service: TOTP işlemleri servisi.

    Returns:
        Başarı mesajı içeren yanıt.

    Raises:
        HTTPException: Kod geçersizse veya 2FA aktif değilse 400 hatası.
    """
    await service.disable(current_user, data.code)
    return MessageResponse(message="2FA başarıyla devre dışı bırakıldı.")


class BackupCodeCountResponse(BaseModel):
    """Kalan backup kod sayisini tasiyan yanit modeli."""

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
    """Kalan backup kod sayısını getirir.

    Kullanıcının henüz kullanılmamış backup kodlarının sayısını döndürür.
    Backup kodlar azaldığında yenileme önerilir.

    Args:
        current_user: Oturum açmış kullanıcı.
        service: TOTP işlemleri servisi.

    Returns:
        Kalan backup kod sayısı ve bilgi mesajı.

    Raises:
        HTTPException: 2FA aktif değilse 400 hatası.
    """
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
