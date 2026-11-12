from typing import List, Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Float, Boolean, Text, JSON, Enum as SQLEnum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from app.models.enums import SourceType, SyncStatus, StandardField

if TYPE_CHECKING:
    from app.models.workspace import Workspace
    from app.models.recruiter import RecruiterProfile


class DataSource(Base, TimestampMixin):
    """
    Connected data source: Google Sheet URL, uploaded Excel, or CSV file.
    Can belong to an individual recruiter or be a team master sheet.
    """
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    recruiter_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("recruiter_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    source_type: Mapped[SourceType] = mapped_column(
        SQLEnum(SourceType, native_enum=False),
        default=SourceType.GOOGLE_SHEET,
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sheet_id_or_url: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_tab_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        SQLEnum(SyncStatus, native_enum=False),
        default=SyncStatus.PENDING_MAPPING,
        nullable=False
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="data_sources")
    recruiter: Mapped[Optional["RecruiterProfile"]] = relationship("RecruiterProfile", back_populates="data_sources")
    column_mappings: Mapped[List["ColumnMapping"]] = relationship("ColumnMapping", back_populates="data_source", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DataSource {self.name} ({self.source_type}) - {self.sync_status}>"


class ColumnMapping(Base, TimestampMixin):
    """
    Field mappings for standardizing varied spreadsheet headers.
    e.g., source column 'Call Outcome' -> standard field 'call_status'.
    """
    __tablename__ = "column_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    data_source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    standard_field: Mapped[StandardField] = mapped_column(
        SQLEnum(StandardField, native_enum=False),
        nullable=False
    )
    source_column_name: Mapped[str] = mapped_column(String(150), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sample_values: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="column_mappings")

    def __repr__(self) -> str:
        return f"<ColumnMapping {self.source_column_name} -> {self.standard_field} ({self.confidence_score})>"

