from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from app.models.enums import UserRole, SubscriptionTier

if TYPE_CHECKING:
    from app.models.recruiter import RecruiterProfile
    from app.models.data_source import DataSource
    from app.models.taxonomy import StatusTaxonomy
    from app.models.report import HourlyReport
    from app.models.audit import AuditLog


class Workspace(Base, TimestampMixin):
    """
    Tenant boundary for each recruitment agency.
    All agency data is isolated by workspace_id.
    """
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    service_account_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier, native_enum=False),
        default=SubscriptionTier.TRIAL,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="workspace", cascade="all, delete-orphan")
    recruiters: Mapped[List["RecruiterProfile"]] = relationship("RecruiterProfile", back_populates="workspace", cascade="all, delete-orphan")
    data_sources: Mapped[List["DataSource"]] = relationship("DataSource", back_populates="workspace", cascade="all, delete-orphan")
    taxonomies: Mapped[List["StatusTaxonomy"]] = relationship("StatusTaxonomy", back_populates="workspace", cascade="all, delete-orphan")
    hourly_reports: Mapped[List["HourlyReport"]] = relationship("HourlyReport", back_populates="workspace", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="workspace", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Workspace {self.slug} - {self.name}>"


class User(Base, TimestampMixin):
    """
    System users (Agency Owner, Manager, MIS Executive, or Recruiter).
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, native_enum=False),
        default=UserRole.MIS_EXECUTIVE,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="users")
    recruiter_profile: Mapped[Optional["RecruiterProfile"]] = relationship("RecruiterProfile", back_populates="user", uselist=False)
    approved_reports: Mapped[List["HourlyReport"]] = relationship("HourlyReport", back_populates="approved_by")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="actor")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"

