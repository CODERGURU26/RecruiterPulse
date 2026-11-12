from typing import List, Optional, Any, TYPE_CHECKING
from datetime import date, datetime
from sqlalchemy import String, Integer, Float, Date, DateTime, JSON, Text, Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid
from app.models.enums import ReportStatus

if TYPE_CHECKING:
    from app.models.workspace import Workspace, User
    from app.models.recruiter import RecruiterProfile


class HourlyReport(Base, TimestampMixin):
    """
    Consolidated hourly snapshot of agency performance.
    Generated automatically (12 PM - 7 PM), awaiting MIS executive approval before distribution.
    """
    __tablename__ = "hourly_reports"
    __table_args__ = (
        UniqueConstraint("workspace_id", "reporting_date", "hour_slot", name="uq_workspace_report_slot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    reporting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hour_slot: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g., '12:00', '13:00', ..., '19:00'
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus, native_enum=False),
        default=ReportStatus.DRAFT_PENDING_APPROVAL,
        nullable=False,
        index=True
    )
    approved_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pre-calculated team summary metrics
    summary_totals: Mapped[Optional[Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="hourly_reports")
    approved_by: Mapped[Optional["User"]] = relationship("User", back_populates="approved_reports")
    metrics: Mapped[List["RecruiterDailyMetric"]] = relationship(
        "RecruiterDailyMetric",
        back_populates="report",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<HourlyReport {self.reporting_date} {self.hour_slot} - {self.status}>"


class RecruiterDailyMetric(Base, TimestampMixin):
    """
    Calculated cumulative activity metrics per recruiter for an hourly snapshot.
    Zero candidate PII stored - DPDP Act compliant.
    """
    __tablename__ = "recruiter_daily_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    hourly_report_id: Mapped[str] = mapped_column(String(36), ForeignKey("hourly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    recruiter_id: Mapped[str] = mapped_column(String(36), ForeignKey("recruiter_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Roles active for this recruiter on this date (e.g. ["Java Backend", "DevOps"])
    job_roles: Mapped[Optional[Any]] = mapped_column(JSON, default=list, nullable=False)
    
    # Cumulative calling counts
    connected_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_connected_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connected_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0.0 to 100.0%
    
    # Next-day interviews (T+1 from Google Calendar)
    next_day_interviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unassigned_interviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    report: Mapped["HourlyReport"] = relationship("HourlyReport", back_populates="metrics")
    recruiter: Mapped["RecruiterProfile"] = relationship("RecruiterProfile", back_populates="daily_metrics")

    def __repr__(self) -> str:
        return f"<RecruiterDailyMetric Recruiter:{self.recruiter_id} Calls:{self.total_calls} (Conn:{self.connected_calls})>"

