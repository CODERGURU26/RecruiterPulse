import sys
import os

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
    StatusTaxonomy,
    DEFAULT_INDIAN_TAXONOMY_PRESETS,
)


def seed():
    print("🔧 Creating fresh database with workspace + taxonomy (no fake reports)...", flush=True)
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
            print("  ✓ Created Workspace 'Apex Staffing Solutions'", flush=True)

            # Seed Indian Status Taxonomy Presets (23 presets)
            for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS:
                tax = StatusTaxonomy(
                    workspace_id=ws.id,
                    raw_status=raw,
                    category=cat,
                    is_default=True
                )
                db.add(tax)
            db.flush()
            print(f"  ✓ Seeded {len(DEFAULT_INDIAN_TAXONOMY_PRESETS)} Indian recruitment status taxonomy presets", flush=True)

            # Admin User (MIS Lead)
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
            print("  ✓ Created MIS Admin user: Pooja Kulkarni", flush=True)

            # Recruiter Profiles (empty — will be auto-created on file upload)
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
            print("  ✓ Created 3 recruiter profiles: Priya, Rahul, Amit", flush=True)

        db.commit()
        print("\n✅ Database ready! Upload real recruiter spreadsheets to generate live reports.", flush=True)
        print("   No fake reports seeded — all data will come from your real files.\n", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    seed()
