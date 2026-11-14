from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timezone

from app.core.database import get_db
from app.models import (
    HourlyReport,
    RecruiterDailyMetric,
    Workspace,
    User,
    ReportStatus,
    AuditLog,
    AuditAction,
)
from app.schemas.report import (
    HourlyReportResponse,
    RecruiterMetricResponse,
    ReportEditRequest,
    ReportApprovalRequest,
    ReportRejectionRequest,
    WhatsAppExportResponse,
)
from app.services.whatsapp_formatter import WhatsAppFormatter

router = APIRouter(prefix="/reports", tags=["MIS Reports & Approvals"])


def serialize_report(report: HourlyReport) -> HourlyReportResponse:
    metrics_response = []
    for m in report.metrics:
        metrics_response.append(
            RecruiterMetricResponse(
                id=m.id,
                recruiter_id=m.recruiter_id,
                recruiter_name=m.recruiter.full_name if m.recruiter else "Unknown",
                job_roles=m.job_roles or [],
                connected_calls=m.connected_calls,
                not_connected_calls=m.not_connected_calls,
                total_calls=m.total_calls,
                connected_rate=m.connected_rate,
                next_day_interviews=m.next_day_interviews,
                unassigned_interviews=m.unassigned_interviews
            )
        )

    return HourlyReportResponse(
        id=report.id,
        workspace_id=report.workspace_id,
        reporting_date=report.reporting_date,
        hour_slot=report.hour_slot,
        status=report.status,
        approved_by_name=report.approved_by.full_name if report.approved_by else None,
        approved_at=report.approved_at,
        rejection_reason=report.rejection_reason,
        summary_totals=report.summary_totals or {},
        metrics=metrics_response,
        created_at=report.created_at
    )


@router.get("/pending", response_model=Optional[HourlyReportResponse])
def get_pending_report(workspace_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Returns the latest draft report awaiting MIS review and approval.
    """
    report = (
        db.query(HourlyReport)
        .filter(
            HourlyReport.workspace_id == workspace_id,
            HourlyReport.status == ReportStatus.DRAFT_PENDING_APPROVAL
        )
        .order_by(HourlyReport.created_at.desc())
        .first()
    )
    if not report:
        return None
    return serialize_report(report)


@router.get("/latest", response_model=Optional[HourlyReportResponse])
def get_latest_approved_report(workspace_id: str = Query(...), db: Session = Depends(get_db)):
    """
    Returns the most recently approved report for the Management Dashboard.
    """
    report = (
        db.query(HourlyReport)
        .filter(
            HourlyReport.workspace_id == workspace_id,
            HourlyReport.status == ReportStatus.APPROVED
        )
        .order_by(HourlyReport.reporting_date.desc(), HourlyReport.hour_slot.desc())
        .first()
    )
    if not report:
        return None
    return serialize_report(report)


@router.put("/{report_id}/draft", response_model=HourlyReportResponse)
def edit_draft_report(
    report_id: str,
    payload: ReportEditRequest,
    db: Session = Depends(get_db)
):
    """Updates report metrics while a report is still awaiting MIS approval."""
    report = db.query(HourlyReport).filter(HourlyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if report.status != ReportStatus.DRAFT_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only reports awaiting approval can be edited."
        )

    user = db.query(User).filter(
        User.id == payload.approver_user_id,
        User.workspace_id == report.workspace_id
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MIS user not found in this workspace.")

    metrics_by_id = {metric.id: metric for metric in report.metrics}
    submitted_ids = [metric.id for metric in payload.metrics]
    if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != set(metrics_by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submit each recruiter metric in this report exactly once."
        )

    edited_details = []
    total_calls = 0
    connected_calls = 0
    not_connected_calls = 0
    total_interviews = 0

    for edit in payload.metrics:
        metric = metrics_by_id[edit.id]
        connected = edit.connected_calls
        not_connected = edit.not_connected_calls
        total = connected + not_connected
        roles = list(dict.fromkeys(
            role.strip() for role in edit.job_roles if role.strip()
        ))

        if total == 0:
            edited_details.append({
                "metric_id": metric.id,
                "connected_calls": 0,
                "not_connected_calls": 0,
                "job_roles": roles,
                "next_day_interviews": 0,
                "removed_from_report": True
            })
            db.delete(metric)
            continue

        metric.connected_calls = connected
        metric.not_connected_calls = not_connected
        metric.total_calls = total
        metric.connected_rate = round(connected / total * 100, 2) if total else 0.0
        metric.job_roles = roles
        metric.next_day_interviews = edit.next_day_interviews

        edited_details.append({
            "metric_id": metric.id,
            "connected_calls": connected,
            "not_connected_calls": not_connected,
            "job_roles": roles,
            "next_day_interviews": edit.next_day_interviews
        })

        total_calls += total
        connected_calls += connected
        not_connected_calls += not_connected
        total_interviews += edit.next_day_interviews + metric.unassigned_interviews

    report.summary_totals = {
        **(report.summary_totals or {}),
        "total_calls": total_calls,
        "connected_calls": connected_calls,
        "not_connected_calls": not_connected_calls,
        "connected_rate": round(connected_calls / total_calls * 100, 2) if total_calls else 0.0,
        "next_day_interviews": total_interviews,
        "active_recruiters_count": sum(1 for edit in payload.metrics if edit.connected_calls + edit.not_connected_calls > 0)
    }

    audit = AuditLog(
        workspace_id=report.workspace_id,
        actor_user_id=user.id,
        action=AuditAction.REPORT_EDITED,
        details={"report_id": report.id, "metrics": edited_details}
    )
    db.add(audit)
    db.commit()
    db.refresh(report)
    return serialize_report(report)


@router.post("/{report_id}/approve", response_model=HourlyReportResponse)
def approve_report(report_id: str, payload: ReportApprovalRequest, db: Session = Depends(get_db)):
    """
    MIS Executive approves the hourly report.
    Transitions status to APPROVED, records approver identity & timestamp.
    """
    report = db.query(HourlyReport).filter(HourlyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if report.status != ReportStatus.DRAFT_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only reports awaiting approval can be approved."
        )

    user = db.query(User).filter(User.id == payload.approver_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approver user not found.")

    report.status = ReportStatus.APPROVED
    report.approved_by_id = user.id
    report.approved_at = datetime.now(timezone.utc)

    # Record Audit Log
    audit = AuditLog(
        workspace_id=report.workspace_id,
        actor_user_id=user.id,
        action=AuditAction.REPORT_APPROVED,
        details={"report_id": report.id, "slot": report.hour_slot}
    )
    db.add(audit)
    db.commit()
    db.refresh(report)

    return serialize_report(report)


@router.post("/{report_id}/reject", response_model=HourlyReportResponse)
def reject_report(report_id: str, payload: ReportRejectionRequest, db: Session = Depends(get_db)):
    """
    MIS Executive rejects the hourly draft report with a reason.
    """
    report = db.query(HourlyReport).filter(HourlyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    if report.status != ReportStatus.DRAFT_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only reports awaiting approval can be rejected."
        )

    user = db.query(User).filter(User.id == payload.approver_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approver user not found.")

    report.status = ReportStatus.REJECTED
    report.approved_by_id = user.id
    report.rejection_reason = payload.reason

    audit = AuditLog(
        workspace_id=report.workspace_id,
        actor_user_id=user.id,
        action=AuditAction.REPORT_REJECTED,
        details={"report_id": report.id, "reason": payload.reason}
    )
    db.add(audit)
    db.commit()
    db.refresh(report)

    return serialize_report(report)


@router.get("/{report_id}/whatsapp", response_model=WhatsAppExportResponse)
def export_whatsapp(report_id: str, db: Session = Depends(get_db)):
    """
    Generates the pre-formatted WhatsApp string ready for 1-click clipboard copy.
    """
    report = db.query(HourlyReport).filter(HourlyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    metrics_list = []
    for m in report.metrics:
        metrics_list.append({
            "recruiter_name": m.recruiter.full_name if m.recruiter else "Unknown",
            "job_roles": m.job_roles or [],
            "connected_calls": m.connected_calls,
            "not_connected_calls": m.not_connected_calls,
            "total_calls": m.total_calls,
            "connected_rate": m.connected_rate,
            "next_day_interviews": m.next_day_interviews
        })

    approver_name = report.approved_by.full_name if report.approved_by else None
    workspace_name = report.workspace.name if report.workspace else "RecruiterPulse Agency"

    formatted_msg = WhatsAppFormatter.format_report(
        workspace_name=workspace_name,
        reporting_date=report.reporting_date,
        hour_slot=report.hour_slot,
        metrics=metrics_list,
        summary_totals=report.summary_totals or {},
        approver_name=approver_name
    )

    return WhatsAppExportResponse(report_id=report.id, formatted_text=formatted_msg)
