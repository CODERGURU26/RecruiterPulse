from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from app.models.enums import ReportStatus


class RecruiterMetricResponse(BaseModel):
    id: str
    recruiter_id: str
    recruiter_name: str
    job_roles: List[str]
    connected_calls: int
    not_connected_calls: int
    total_calls: int
    connected_rate: float
    next_day_interviews: int
    unassigned_interviews: int

    class Config:
        from_attributes = True


class HourlyReportResponse(BaseModel):
    id: str
    workspace_id: str
    reporting_date: date
    hour_slot: str
    status: ReportStatus
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    summary_totals: Dict[str, Any]
    metrics: List[RecruiterMetricResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class ReportApprovalRequest(BaseModel):
    approver_user_id: str


class ReportRejectionRequest(BaseModel):
    approver_user_id: str
    reason: str


class RecruiterMetricEdit(BaseModel):
    id: str
    job_roles: List[str]
    connected_calls: int = Field(ge=0)
    not_connected_calls: int = Field(ge=0)
    next_day_interviews: int = Field(ge=0)


class ReportEditRequest(BaseModel):
    approver_user_id: str
    metrics: List[RecruiterMetricEdit]


class WhatsAppExportResponse(BaseModel):
    report_id: str
    formatted_text: str
