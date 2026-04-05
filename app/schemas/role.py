"""Role şemaları — request/response modelleri."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.permissions import Permission


class RoleResponse(BaseModel):
    """Rol bilgisi response şeması.

    Attributes:
        id: Rol UUID'si
        name: Rol adı
        description: Rol açıklaması
        is_system: Sistem rolü mü (silinemez)
        permissions: Bu role atanmış permission listesi
    """

    id: UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_role(cls, role: object) -> RoleResponse:
        """Role ORM nesnesinden RoleResponse oluşturur."""
        from app.db.models.role import Role as RoleModel

        if not isinstance(role, RoleModel):
            raise TypeError(f"Expected Role, got {type(role)}")
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permissions=sorted(role.permission_set),
        )


class RoleInfo(BaseModel):
    """Kullanıcı response'larında gömülü rol özet bilgisi.

    Attributes:
        id: Rol UUID'si
        name: Rol adı
        is_system: Sistem rolü mü
    """

    id: UUID
    name: str
    is_system: bool

    model_config = {"from_attributes": True}


class CreateRoleRequest(BaseModel):
    """Yeni rol oluşturma isteği.

    Attributes:
        name: Benzersiz rol adı (1-50 karakter)
        description: Opsiyonel rol açıklaması
        permissions: Başlangıç permission listesi
    """

    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    description: str | None = Field(None, max_length=255)
    permissions: list[Permission] = Field(default_factory=list)


class UpdateRoleRequest(BaseModel):
    """Rol güncelleme isteği.

    Attributes:
        description: Yeni açıklama
        permissions: Yeni permission seti (mevcut setin yerini alır)
    """

    description: str | None = Field(None, max_length=255)
    permissions: list[Permission] | None = None


class AssignRoleRequest(BaseModel):
    """Kullanıcıya rol atama isteği.

    Attributes:
        role_name: Atanacak rolün adı
    """

    role_name: str = Field(..., min_length=1, max_length=50)
