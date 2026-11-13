from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from app.models.enums import CallCategory

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class StatusTaxonomy(Base, TimestampMixin):
    """
    Standardization taxonomy for varied recruitment call statuses.
    Categorizes terms like 'RNR', 'Switched Off', 'Interested' into CONNECTED / NOT_CONNECTED.
    """
    __tablename__ = "status_taxonomies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "raw_status", name="uq_workspace_raw_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_status: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[CallCategory] = mapped_column(
        SQLEnum(CallCategory, native_enum=False),
        nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="taxonomies")

    def __repr__(self) -> str:
        return f"<StatusTaxonomy '{self.raw_status}' -> {self.category}>"


# Default Indian recruitment presets for workspace initialization
DEFAULT_INDIAN_TAXONOMY_PRESETS = [
    # Connected (Productive)
    ("connected", CallCategory.CONNECTED),
    ("spoke", CallCategory.CONNECTED),
    ("interested", CallCategory.CONNECTED),
    ("screening done", CallCategory.CONNECTED),
    ("profile shared", CallCategory.CONNECTED),
    ("l1 scheduled", CallCategory.CONNECTED),
    ("interview scheduled", CallCategory.CONNECTED),
    ("salary discussed", CallCategory.CONNECTED),
    ("call back requested", CallCategory.CONNECTED),
    ("already placed", CallCategory.CONNECTED),
    ("not interested", CallCategory.CONNECTED),  # Spoke to candidate, outcome recorded
    ("not connected", CallCategory.NOT_CONNECTED),
    # Not Connected (Unproductive)
    ("rnr", CallCategory.NOT_CONNECTED),
    ("ringing no response", CallCategory.NOT_CONNECTED),
    ("busy", CallCategory.NOT_CONNECTED),
    ("switched off", CallCategory.NOT_CONNECTED),
    ("out of coverage", CallCategory.NOT_CONNECTED),
    ("wrong number", CallCategory.NOT_CONNECTED),
    ("invalid number", CallCategory.NOT_CONNECTED),
    ("call disconnected", CallCategory.NOT_CONNECTED),
    ("not reachable", CallCategory.NOT_CONNECTED),
    ("voicemail", CallCategory.NOT_CONNECTED),
    # Ignored
    ("duplicate", CallCategory.IGNORED),
    ("do not call", CallCategory.IGNORED),
]
