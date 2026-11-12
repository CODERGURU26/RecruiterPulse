import sys
import os
from datetime import date

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


def seed():
    print("Seeding database with live agency workspace and draft report...", flush=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if workspace already exists
        ws = db.query(Workspace).filter(Workspace.slug == "apex-staffing").first()
        if not ws:
            ws = Workspace(
                id="ws-apex-101",
                name="Apex Staffing Solutions",
                slug="apex-staffing",
                timezone="Asia/Kolkata",
                service_account_email="sync@recruiterpulse.iam.gserviceaccount.com"
            )
            db.add(ws)
            db.flush()
            print("✓ Created Workspace 'Apex Staffing Solutions'", flush=True)

            # Seed Indian Status Presets
            for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS:
                tax = StatusTaxonomy(
                    workspace_id=ws.id,
                    raw_status=raw,
                    category=cat,
                    is_default=True
                )
                db.add(tax)
            db.flush()

            # Admin User
            admin_user = User(
                id="usr-admin",
                workspace_id=ws.id,
                email="pooja@apexstaffing.in",
                hashed_password="hashed_secure_password",
                full_name="Pooja Kulkarni (MIS Lead)",
                role=UserRole.MIS_EXECUTIVE
            )
            db.add(admin_user)
            db.flush()

            # Recruiters
            rec1 = RecruiterProfile(
                id="rec-1",
                workspace_id=ws.id,
                full_name="Priya Sharma",
                email="priya@apexstaffing.in",
                calendar_identifier="priya@apexstaffing.in"
            )
            rec2 = RecruiterProfile(
                id="rec-2",
                workspace_id=ws.id,
                full_name="Rahul Verma",
                email="rahul@apexstaffing.in",
                calendar_identifier="rahul@apexstaffing.in"
            )
            rec3 = RecruiterProfile(
                id="rec-3",
                workspace_id=ws.id,
                full_name="Amit Patel",
                email="amit@apexstaffing.in",
                calendar_identifier="amit@apexstaffing.in"
            )
            db.add_all([rec1, rec2, rec3])
            db.flush()

            # Data Sources
            ds1 = DataSource(
                workspace_id=ws.id,
                recruiter_id=rec1.id,
                source_type=SourceType.GOOGLE_SHEET,
                name="Priya - Calling Sheet",
                sheet_id_or_url="https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
                sync_status=SyncStatus.ACTIVE
            )
            ds2 = DataSource(
                workspace_id=ws.id,
                recruiter_id=rec2.id,
                source_type=SourceType.GOOGLE_SHEET,
                name="Rahul - Calling Sheet",
                sheet_id_or_url="https://docs.google.com/spreadsheets/d/1KLoMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upxx/edit",
                sync_status=SyncStatus.ACTIVE
            )
            db.add_all([ds1, ds2])
            db.flush()

        # Seed Draft Report for today's 15:00 slot if not existing
        today = date.today()
        report = db.query(HourlyReport).filter(
            HourlyReport.workspace_id == ws.id,
            HourlyReport.reporting_date == today,
            HourlyReport.hour_slot == "15:00"
        ).first()

        if not report:
            report = HourlyReport(
                id="rep-draft-1500",
                workspace_id=ws.id,
                reporting_date=today,
                hour_slot="15:00",
                status=ReportStatus.DRAFT_PENDING_APPROVAL,
                summary_totals={
                    "total_calls": 128,
                    "connected_calls": 84,
                    "not_connected_calls": 44,
                    "connected_rate": 65.62,
                    "next_day_interviews": 6,
                    "active_recruiters_count": 3
                }
            )
            db.add(report)
            db.flush()

            m1 = RecruiterDailyMetric(
                hourly_report_id=report.id,
                recruiter_id="rec-1",
                job_roles=["Java Backend", "DevOps"],
                connected_calls=28,
                not_connected_calls=14,
                total_calls=42,
                connected_rate=66.67,
                next_day_interviews=3,
                unassigned_interviews=0
            )
            m2 = RecruiterDailyMetric(
                hourly_report_id=report.id,
                recruiter_id="rec-2",
                job_roles=["React Frontend"],
                connected_calls=18,
                not_connected_calls=17,
                total_calls=35,
                connected_rate=51.43,
                next_day_interviews=1,
                unassigned_interviews=0
            )
            m3 = RecruiterDailyMetric(
                hourly_report_id=report.id,
                recruiter_id="rec-3",
                job_roles=["Data Engineer", "AWS Cloud"],
                connected_calls=38,
                not_connected_calls=13,
                total_calls=51,
                connected_rate=74.51,
                next_day_interviews=2,
                unassigned_interviews=0
            )
            db.add_all([m1, m2, m3])

        db.commit()
        print("✓ Database successfully seeded with live agency data & pending draft report!", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    seed()

