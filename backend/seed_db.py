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
    print("Creating fresh database with workspace + taxonomy (no fake reports)...", flush=True)
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
            print("  Created Workspace 'Apex Staffing Solutions'", flush=True)

            # Seed Indian Status Taxonomy Presets (23 presets)
            for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS:
                existing_taxonomy = db.query(StatusTaxonomy).filter(
                    StatusTaxonomy.workspace_id == ws.id,
                    StatusTaxonomy.raw_status == raw
                ).first()
                if not existing_taxonomy:
                    db.add(StatusTaxonomy(
                        workspace_id=ws.id,
                        raw_status=raw,
                        category=cat,
                        is_default=True
                    ))
            db.flush()
            print(f"  Seeded {len(DEFAULT_INDIAN_TAXONOMY_PRESETS)} Indian recruitment status taxonomy presets", flush=True)

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
            print("  Created MIS Admin user: Pooja Kulkarni", flush=True)

            # Recruiter Profiles (empty — will be auto-created on file upload)
            recruiters = [
                ("Priya Sharma", "priya@apexstaffing.in"),
                ("Rahul Verma", "rahul@apexstaffing.in"),
                ("Amit Patel", "amit@apexstaffing.in"),
            ]
            for name, email in recruiters:
                existing_recruiter = db.query(RecruiterProfile).filter(
                    RecruiterProfile.workspace_id == ws.id,
                    (RecruiterProfile.email == email) |
                    (RecruiterProfile.full_name == name)
                ).first()
                if existing_recruiter:
                    if not existing_recruiter.email:
                        existing_recruiter.email = email
                    if not existing_recruiter.calendar_identifier:
                        existing_recruiter.calendar_identifier = email
                else:
                    db.add(RecruiterProfile(
                        workspace_id=ws.id,
                        full_name=name,
                        email=email,
                        calendar_identifier=email
                    ))
            db.flush()
            print("  Ensured recruiter profiles: Priya, Rahul, Amit", flush=True)

        db.commit()
        print("\nDatabase ready! Upload real recruiter spreadsheets to generate live reports.", flush=True)
        print("   No fake reports seeded; all data will come from your real files.\n", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    seed()
