from typing import Optional, Any, TYPE_CHECKING
from sqlalchemy import String, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from app.models.enums import AuditAction

if TYPE_CHECKING:
    from app.models.workspace import Workspace, User


class AuditLog(Base, TimestampMixin):
    """
    Immutable audit trail for critical agency actions:
    Report approvals, rejections, manual edits, column mapping confirmations.
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction, native_enum=False),
        nullable=False,
        index=True
    )
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="audit_logs")
    actor: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by User:{self.actor_user_id}>"

