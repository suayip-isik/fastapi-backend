"""Role ve RolePermission modelleri."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, BaseModel, SoftDeleteMixin


class Role(SoftDeleteMixin, BaseModel):
    """Kullanıcı rolü modeli.

    Her rol bir isim, açıklama ve permission setine sahiptir.
    Sistem rolleri (admin, user, moderator) is_system=True ile
    işaretlenir ve silinemez.

    Attributes:
        name: Benzersiz rol adı (ör: "admin", "accountant")
        description: Rol açıklaması
        is_system: True ise sistem rolü — silinemez, adı değiştirilemez
        permissions: Bu role atanmış permission kaydları

    Note:
        - Sistem rolleri seed sırasında oluşturulur
        - Özel roller admin API'si üzerinden yönetilir
        - permission_set property ile string set'e erişilir
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list[RolePermission]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def permission_set(self) -> set[str]:
        """Bu role atanmış permission string'lerini set olarak döner."""
        return {rp.permission for rp in self.permissions}

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class RolePermission(Base):
    """Rol-permission ilişki tablosu.

    Bir rolün sahip olduğu permission'ları saklar.
    Permission değerleri Permission enum'unun string değerleridir
    (ör: "users:read", "admin:access").

    Attributes:
        role_id: Bağlı rol UUID'si
        permission: Permission string değeri (ör: "users:write")
    """

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission: Mapped[str] = mapped_column(String(100), primary_key=True)

    role: Mapped[Role] = relationship("Role", back_populates="permissions")
