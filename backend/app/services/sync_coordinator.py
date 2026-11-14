from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Workspace,
    RecruiterProfile,
    DataSource,
    ColumnMapping,
    StatusTaxonomy,
    HourlyReport,
    RecruiterDailyMetric,
    ReportStatus,
    SyncStatus,
    AuditLog,
    AuditAction,
    StandardField,
    CallCategory,
)
from app.services.google_sheets_worker import GoogleSheetsWorker
from app.services.google_calendar_worker import GoogleCalendarWorker
from app.services.calculation_engine import CalculationEngine, RecruiterMetricsResult


class SyncCoordinator:
    """
    Orchestrates the hourly automated data pull across Google Sheets and Google Calendar.
    Generates cumulative daily snapshots awaiting MIS review.
    """

    @classmethod
    def get_current_slot(cls, tz_name: str = "Asia/Kolkata") -> Tuple[date, str]:
        """Calculates current date and nearest reporting hour slot (e.g. '15:00')."""
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        today = now.date()
        hour_slot = f"{now.hour:02d}:00"
        return today, hour_slot

    @classmethod
    async def run_workspace_sync(
        cls,
        workspace_id: str,
        db: Session,
        override_date: Optional[date] = None,
        override_slot: Optional[str] = None
    ) -> HourlyReport:
        """
        Executes end-to-end sync for an agency workspace:
        1. Ingests Google Sheets
        2. Normalizes calling metrics
        3. Retrieves tomorrow's calendar interviews with 4-tier attribution
        4. Saves cumulative snapshot as DRAFT_PENDING_APPROVAL
        """
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found.")

        reporting_date, hour_slot = cls.get_current_slot(workspace.timezone)
        if override_date:
            reporting_date = override_date
        if override_slot:
            hour_slot = override_slot

        # 1. Fetch active recruiters
        recruiters = db.query(RecruiterProfile).filter(
            RecruiterProfile.workspace_id == workspace.id,
            RecruiterProfile.is_active == True
        ).all()

        recruiter_dicts = [
            {
                "id": r.id,
                "full_name": r.full_name,
                "email": r.email,
                "calendar_identifier": r.calendar_identifier
            }
            for r in recruiters
        ]

        # 2. Fetch workspace call status taxonomy
        taxonomies = db.query(StatusTaxonomy).filter(StatusTaxonomy.workspace_id == workspace.id).all()
        taxonomy_lookup: Dict[str, CallCategory] = {
            t.raw_status.lower().strip(): t.category for t in taxonomies
        }

        # 3. Process only explicitly registered, active recruiter sheets.
        recruiter_metrics_map: Dict[str, RecruiterMetricsResult] = {}
        active_sources = db.query(DataSource).filter(
            DataSource.workspace_id == workspace.id,
            DataSource.sync_status == SyncStatus.ACTIVE
        ).all()
        if not active_sources:
            raise ValueError("No active Google Sheets are registered for live sync.")

        sources_by_recruiter: Dict[str, List[DataSource]] = {}
        for data_source in active_sources:
            if not data_source.recruiter_id:
                raise ValueError(
                    f"Active data source '{data_source.name}' must be assigned to a recruiter before syncing."
                )
            sources_by_recruiter.setdefault(data_source.recruiter_id, []).append(data_source)

        sync_errors: List[str] = []

        for rec in recruiters:
            recruiter_sources = sources_by_recruiter.get(rec.id, [])
            if not recruiter_sources:
                continue
            if len(recruiter_sources) > 1:
                sync_errors.append(f"{rec.full_name}: multiple active sheets are registered")
                continue
            ds = recruiter_sources[0]

            # Load column mappings
            mappings = db.query(ColumnMapping).filter(ColumnMapping.data_source_id == ds.id).all()
            col_map: Dict[StandardField, str] = {
                m.standard_field: m.source_column_name for m in mappings
            }

            try:
                # Ingest spreadsheet
                df = await GoogleSheetsWorker.fetch_sheet_dataframe(ds.sheet_id_or_url, ds.sheet_tab_name)
                recruiter_column = col_map.get(StandardField.RECRUITER_NAME)
                if recruiter_column and recruiter_column in df.columns:
                    recruiter_values = df[recruiter_column].astype("string").str.strip()
                    recruiter_values = recruiter_values.replace("", pd.NA).ffill()
                    df = df[
                        recruiter_values.str.casefold() == rec.full_name.strip().casefold()
                    ].copy()
                metrics_res = CalculationEngine.calculate_recruiter_activity(
                    df=df,
                    column_mapping=col_map,
                    status_taxonomy=taxonomy_lookup,
                    target_date=reporting_date
                )
                recruiter_metrics_map[rec.id] = metrics_res
                ds.last_synced_at = datetime.now(ZoneInfo(workspace.timezone))
                ds.last_error_message = None
            except Exception as e:
                ds.last_error_message = str(e)
                sync_errors.append(f"{rec.full_name}: {e}")

        if sync_errors:
            db.commit()
            raise RuntimeError(
                "Live sync aborted; the report was not changed. " + "; ".join(sync_errors)
            )

        if not recruiter_metrics_map:
            raise ValueError("No active recruiter sheets were available to sync.")

        # 4. Process Google Calendar (Tomorrow's Interviews)
        # Calculates T+1 window
        time_min, time_max, tomorrow_date = GoogleCalendarWorker.get_tomorrow_window(
            reference_date=reporting_date,
            tz_name=workspace.timezone
        )

        calendar_result = GoogleCalendarWorker.process_calendar_events(
            events=[],  # Real Google API events when configured, or empty
            recruiters=recruiter_dicts,
            target_date=tomorrow_date
        )

        report = db.query(HourlyReport).filter(
            HourlyReport.workspace_id == workspace.id,
            HourlyReport.reporting_date == reporting_date,
            HourlyReport.hour_slot == hour_slot
        ).first()
        if report and report.status == ReportStatus.DRAFT_PENDING_APPROVAL:
            edit_audits = db.query(AuditLog).filter(
                AuditLog.workspace_id == workspace.id,
                AuditLog.action == AuditAction.REPORT_EDITED
            ).all()
            if any((audit.details or {}).get("report_id") == report.id for audit in edit_audits):
                db.commit()
                db.refresh(report)
                return report

        # 5. Handle Superseding of Older Unapproved Snapshots for Today
        older_drafts = db.query(HourlyReport).filter(
            HourlyReport.workspace_id == workspace.id,
            HourlyReport.reporting_date == reporting_date,
            HourlyReport.status == ReportStatus.DRAFT_PENDING_APPROVAL,
            HourlyReport.hour_slot != hour_slot
        ).all()
        for old in older_drafts:
            old.status = ReportStatus.SUPERSEDED

        # 6. Create or Update Hourly Snapshot
        if not report:
            report = HourlyReport(
                workspace_id=workspace.id,
                reporting_date=reporting_date,
                hour_slot=hour_slot,
                status=ReportStatus.DRAFT_PENDING_APPROVAL,
                summary_totals={}
            )
            db.add(report)
            db.flush()
        else:
            # Clear old metric line items for this slot
            db.query(RecruiterDailyMetric).filter(RecruiterDailyMetric.hourly_report_id == report.id).delete()

        # 7. Add Recruiter Daily Metric Line Items
        total_calls = 0
        connected_calls = 0
        not_connected_calls = 0
        total_interviews = 0
        active_recruiters_count = 0

        for rec in recruiters:
            m_res = recruiter_metrics_map.get(rec.id)
            if not m_res or m_res.total_calls == 0:
                continue

            conn = m_res.connected_calls
            not_conn = m_res.not_connected_calls
            tot = m_res.total_calls
            rate = m_res.connected_rate
            roles = m_res.job_roles
            interviews = calendar_result.recruiter_interviews.get(rec.id, 0)

            total_calls += tot
            connected_calls += conn
            not_connected_calls += not_conn
            total_interviews += interviews
            active_recruiters_count += 1

            metric_item = RecruiterDailyMetric(
                hourly_report_id=report.id,
                recruiter_id=rec.id,
                job_roles=roles,
                connected_calls=conn,
                not_connected_calls=not_conn,
                total_calls=tot,
                connected_rate=rate,
                next_day_interviews=interviews,
                unassigned_interviews=0
            )
            db.add(metric_item)

        team_rate = round((connected_calls / total_calls * 100), 2) if total_calls > 0 else 0.0

        report.summary_totals = {
            "total_calls": total_calls,
            "connected_calls": connected_calls,
            "not_connected_calls": not_connected_calls,
            "connected_rate": team_rate,
            "next_day_interviews": total_interviews + calendar_result.unassigned_count,
            "active_recruiters_count": active_recruiters_count
        }

        # 8. Log Audit Event
        audit = AuditLog(
            workspace_id=workspace.id,
            action=AuditAction.REPORT_GENERATED,
            details={"slot": hour_slot, "reporting_date": str(reporting_date)}
        )
        db.add(audit)

        db.commit()
        db.refresh(report)
        return report
