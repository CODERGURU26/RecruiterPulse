import sys
import os
import io
from datetime import date

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, Base, engine
from app.api.v1.workspaces import create_workspace, add_recruiter, list_recruiters
from app.api.v1.data_sources import create_data_source, confirm_mappings
from app.api.v1.reports import get_pending_report, approve_report, export_whatsapp
from app.schemas.workspace import WorkspaceCreate
from app.schemas.recruiter import RecruiterCreate
from app.schemas.data_source import DataSourceCreate, ConfirmMappingRequest
from app.schemas.report import ReportApprovalRequest
from app.models import HourlyReport, RecruiterDailyMetric, ReportStatus, StandardField, SourceType


def test_api_endpoints_direct():
    print("=" * 60, flush=True)
    print("TESTING RECRUITERPULSE FASTAPI ENDPOINTS & LOGIC DIRECTLY", flush=True)
    print("=" * 60, flush=True)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Test POST /api/v1/workspaces
        ws_in = WorkspaceCreate(
            name="Apex Human Capital",
            slug="apex-human-capital",
            admin_name="Manish Kothari",
            admin_email="manish@apexhc.in",
            admin_password="secure_password_apex",
            timezone="Asia/Kolkata"
        )
        ws_res = create_workspace(payload=ws_in, db=db)
        print(f"✓ POST /api/v1/workspaces -> Workspace '{ws_res.name}' created (ID: {ws_res.id})", flush=True)

        # 2. Test POST /api/v1/workspaces/{id}/recruiters
        rec_in = RecruiterCreate(
            full_name="Deepa Nair",
            email="deepa@apexhc.in",
            calendar_identifier="deepa@apexhc.in"
        )
        rec_res = add_recruiter(workspace_id=ws_res.id, payload=rec_in, db=db)
        print(f"✓ POST /api/v1/workspaces/{{id}}/recruiters -> Recruiter '{rec_res.full_name}' added", flush=True)

        # 3. Test GET /api/v1/workspaces/{id}/recruiters
        rec_list = list_recruiters(workspace_id=ws_res.id, db=db)
        assert len(rec_list) == 1
        print(f"✓ GET /api/v1/workspaces/{{id}}/recruiters -> Found {len(rec_list)} active recruiter(s)", flush=True)

        # 4. Test POST /api/v1/data-sources/{id}
        ds_in = DataSourceCreate(
            recruiter_id=rec_res.id,
            source_type=SourceType.GOOGLE_SHEET,
            name="Deepa - Calling Sheet Q4",
            sheet_id_or_url="https://docs.google.com/spreadsheets/d/abc123demo/edit"
        )
        ds_res = create_data_source(workspace_id=ws_res.id, payload=ds_in, db=db)
        print(f"✓ POST /api/v1/data-sources -> Registered data source '{ds_res.name}'", flush=True)

        # 5. Test POST /api/v1/data-sources/confirm-mappings
        confirm_req = ConfirmMappingRequest(
            data_source_id=ds_res.id,
            mappings={
                StandardField.ACTIVITY_DATE: "Calling Date",
                StandardField.CALL_STATUS: "Call Outcome",
                StandardField.CANDIDATE_REF: "Mobile",
                StandardField.JOB_ROLE: "Role"
            }
        )
        confirm_res = confirm_mappings(payload=confirm_req, db=db)
        print(f"✓ POST /api/v1/data-sources/confirm-mappings -> {confirm_res['message']} (Status: {confirm_res['status']})", flush=True)

        # 6. Seed a Draft Hourly Report in DB
        draft = HourlyReport(
            workspace_id=ws_res.id,
            reporting_date=date.today(),
            hour_slot="16:00",
            status=ReportStatus.DRAFT_PENDING_APPROVAL,
            summary_totals={
                "total_calls": 48,
                "connected_calls": 31,
                "not_connected_calls": 17,
                "connected_rate": 64.58,
                "next_day_interviews": 4,
                "active_recruiters_count": 1
            }
        )
        db.add(draft)
        db.flush()

        metric = RecruiterDailyMetric(
            hourly_report_id=draft.id,
            recruiter_id=rec_res.id,
            job_roles=["Python Fullstack", "React Native"],
            connected_calls=31,
            not_connected_calls=17,
            total_calls=48,
            connected_rate=64.58,
            next_day_interviews=4,
            unassigned_interviews=0
        )
        db.add(metric)
        db.commit()

        # 7. Test GET /api/v1/reports/pending
        pending_report = get_pending_report(workspace_id=ws_res.id, db=db)
        assert pending_report is not None
        assert pending_report.status == ReportStatus.DRAFT_PENDING_APPROVAL
        print(f"✓ GET /api/v1/reports/pending -> Retrieved Slot {pending_report.hour_slot} awaiting review", flush=True)

        # Fetch admin user id
        from app.models import User
        admin_user = db.query(User).filter(User.workspace_id == ws_res.id).first()

        # 8. Test POST /api/v1/reports/{id}/approve
        approval_req = ReportApprovalRequest(approver_user_id=admin_user.id)
        approved_report = approve_report(report_id=draft.id, payload=approval_req, db=db)
        assert approved_report.status == ReportStatus.APPROVED
        assert approved_report.approved_by_name == "Manish Kothari"
        print(f"✓ POST /api/v1/reports/{{id}}/approve -> Approved by '{approved_report.approved_by_name}'", flush=True)

        # 9. Test GET /api/v1/reports/{id}/whatsapp
        whatsapp_res = export_whatsapp(report_id=draft.id, db=db)
        assert "Apex Human Capital" in whatsapp_res.formatted_text
        assert "Manish Kothari" in whatsapp_res.formatted_text
        print(f"✓ GET /api/v1/reports/{{id}}/whatsapp -> WhatsApp summary generated successfully:\n", flush=True)
        print("-" * 50, flush=True)
        print(whatsapp_res.formatted_text, flush=True)
        print("-" * 50, flush=True)

        print("\nALL FASTAPI ENDPOINTS & LOGIC VERIFIED WITH 100% SUCCESS!", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    test_api_endpoints_direct()

