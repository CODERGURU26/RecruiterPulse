import sys
import os
from datetime import date, datetime, timezone

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base, engine, SessionLocal
from app.models import (
    Workspace,
    User,
    UserRole,
    RecruiterProfile,
    DataSource,
    SourceType,
    SyncStatus,
    ColumnMapping,
    StandardField,
    StatusTaxonomy,
    CallCategory,
    DEFAULT_INDIAN_TAXONOMY_PRESETS,
    HourlyReport,
    ReportStatus,
    RecruiterDailyMetric,
    AuditLog,
    AuditAction,
)


def run_test():
    print("Initializing test database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")

    db = SessionLocal()
    try:
        print("\nTesting Model Insertion & Relationships...")
        # 1. Create Workspace
        workspace = Workspace(
            name="Apex Staffing Solutions",
            slug="apex-staffing",
            timezone="Asia/Kolkata",
            service_account_email="sync@recruiterpulse.iam.gserviceaccount.com"
        )
        db.add(workspace)
        db.flush()
        print(f"✓ Created Workspace: {workspace.name} (ID: {workspace.id})")

        # 2. Seed Default Indian Call Status Taxonomies
        for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS:
            tax = StatusTaxonomy(
                workspace_id=workspace.id,
                raw_status=raw,
                category=cat,
                is_default=True
            )
            db.add(tax)
        db.flush()
        print(f"✓ Seeded {len(DEFAULT_INDIAN_TAXONOMY_PRESETS)} default Indian status taxonomy mappings")

        # 3. Create MIS Executive User
        mis_user = User(
            workspace_id=workspace.id,
            email="mis@apexstaffing.in",
            hashed_password="hashed_secure_password_example",
            full_name="Pooja Kulkarni",
            role=UserRole.MIS_EXECUTIVE
        )
        db.add(mis_user)
        db.flush()
        print(f"✓ Created MIS User: {mis_user.full_name} ({mis_user.role})")

        # 4. Create Recruiter Profiles
        recruiter1 = RecruiterProfile(
            workspace_id=workspace.id,
            full_name="Priya Sharma",
            email="priya@apexstaffing.in",
            calendar_identifier="priya@apexstaffing.in"
        )
        recruiter2 = RecruiterProfile(
            workspace_id=workspace.id,
            full_name="Rahul Verma",
            email="rahul@apexstaffing.in",
            calendar_identifier="rahul@apexstaffing.in"
        )
        db.add_all([recruiter1, recruiter2])
        db.flush()
        print(f"✓ Created Recruiters: {recruiter1.full_name}, {recruiter2.full_name}")

        # 5. Create Data Source & Column Mappings
        data_source = DataSource(
            workspace_id=workspace.id,
            recruiter_id=recruiter1.id,
            source_type=SourceType.GOOGLE_SHEET,
            name="Priya - Daily Calling Tracker",
            sheet_id_or_url="https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
            sheet_tab_name="Nov 2026",
            sync_status=SyncStatus.ACTIVE
        )
        db.add(data_source)
        db.flush()

        mapping1 = ColumnMapping(
            data_source_id=data_source.id,
            standard_field=StandardField.ACTIVITY_DATE,
            source_column_name="Calling Date",
            confidence_score=0.95,
            is_confirmed=True
        )
        mapping2 = ColumnMapping(
            data_source_id=data_source.id,
            standard_field=StandardField.CALL_STATUS,
            source_column_name="Call Outcome",
            confidence_score=0.92,
            is_confirmed=True
        )
        db.add_all([mapping1, mapping2])
        db.flush()
        print(f"✓ Connected DataSource '{data_source.name}' with {len(data_source.column_mappings)} confirmed column mappings")

        # 6. Create Hourly Snapshot Report (3:00 PM)
        report = HourlyReport(
            workspace_id=workspace.id,
            reporting_date=date.today(),
            hour_slot="15:00",
            status=ReportStatus.DRAFT_PENDING_APPROVAL,
            summary_totals={
                "total_calls": 77,
                "connected_calls": 46,
                "not_connected_calls": 31,
                "connected_rate": 59.74,
                "next_day_interviews": 4,
                "active_recruiters_count": 2
            }
        )
        db.add(report)
        db.flush()

        # 7. Add Recruiter Daily Metrics
        metric1 = RecruiterDailyMetric(
            hourly_report_id=report.id,
            recruiter_id=recruiter1.id,
            job_roles=["Java Backend", "DevOps"],
            connected_calls=28,
            not_connected_calls=14,
            total_calls=42,
            connected_rate=66.67,
            next_day_interviews=3,
            unassigned_interviews=0
        )
        metric2 = RecruiterDailyMetric(
            hourly_report_id=report.id,
            recruiter_id=recruiter2.id,
            job_roles=["React Frontend"],
            connected_calls=18,
            not_connected_calls=17,
            total_calls=35,
            connected_rate=51.43,
            next_day_interviews=1,
            unassigned_interviews=0
        )
        db.add_all([metric1, metric2])
        db.flush()
        print(f"✓ Generated Draft Report {report.hour_slot} with 2 recruiter metrics")

        # 8. Simulate MIS Approval
        report.status = ReportStatus.APPROVED
        report.approved_by_id = mis_user.id
        report.approved_at = datetime.now(timezone.utc)

        audit = AuditLog(
            workspace_id=workspace.id,
            actor_user_id=mis_user.id,
            action=AuditAction.REPORT_APPROVED,
            details={"report_id": report.id, "slot": report.hour_slot}
        )
        db.add(audit)
        db.commit()

        print(f"✓ Report successfully Approved by {mis_user.full_name} and Audit Log recorded!")

        # 9. Verification Query
        fetched_report = db.query(HourlyReport).filter_by(id=report.id).first()
        assert fetched_report is not None
        assert fetched_report.status == ReportStatus.APPROVED
        assert len(fetched_report.metrics) == 2
        print(f"\nVerification Query Passed:")
        print(f"  - Report Slot: {fetched_report.hour_slot}")
        print(f"  - Status: {fetched_report.status.value}")
        print(f"  - Approver: {fetched_report.approved_by.full_name}")
        for m in fetched_report.metrics:
            print(f"    * {m.recruiter.full_name}: {m.total_calls} Calls ({m.connected_calls} Conn, {m.not_connected_calls} Not Conn) | Tomorrow Interviews: {m.next_day_interviews}")

        print("\nAll database schema tests passed with 100% success!")

    finally:
        db.close()


if __name__ == "__main__":
    run_test()

