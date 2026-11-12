from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.workspace import Workspace, User
    from app.models.data_source import DataSource
    from app.models.report import RecruiterDailyMetric


class RecruiterProfile(Base, TimestampMixin):
    """
    Agency roster of recruiters.
    Can exist independently of a system User login (since recruiters usually only edit sheets).
    """
    __tablename__ = "recruiter_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    calendar_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="recruiters")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="recruiter_profile")
    data_sources: Mapped[List["DataSource"]] = relationship("DataSource", back_populates="recruiter", cascade="all, delete-orphan")
    daily_metrics: Mapped[List["RecruiterDailyMetric"]] = relationship("RecruiterDailyMetric", back_populates="recruiter")

    def __repr__(self) -> str:
        return f"<RecruiterProfile {self.full_name}>"

