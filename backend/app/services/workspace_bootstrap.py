from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    DEFAULT_INDIAN_TAXONOMY_PRESETS,
    RecruiterProfile,
    StatusTaxonomy,
    User,
    UserRole,
    Workspace,
)


def ensure_default_workspace(db: Session) -> Workspace:
    workspace = db.query(Workspace).filter(
        Workspace.id == "ws-apex-101"
    ).first() or db.query(Workspace).filter(
        Workspace.slug == "apex-staffing"
    ).first()

    if not workspace:
        workspace = Workspace(
            id="ws-apex-101",
            name="Apex Staffing Solutions",
            slug="apex-staffing",
            timezone="Asia/Kolkata",
            service_account_email=settings.GOOGLE_SERVICE_ACCOUNT_EMAIL
        )
        db.add(workspace)
        db.flush()
    else:
        workspace.service_account_email = settings.GOOGLE_SERVICE_ACCOUNT_EMAIL

    for raw_status, category in DEFAULT_INDIAN_TAXONOMY_PRESETS:
        existing_taxonomy = db.query(StatusTaxonomy).filter(
            StatusTaxonomy.workspace_id == workspace.id,
            StatusTaxonomy.raw_status == raw_status
        ).first()
        if not existing_taxonomy:
            db.add(StatusTaxonomy(
                workspace_id=workspace.id,
                raw_status=raw_status,
                category=category,
                is_default=True
            ))

    admin_user = db.query(User).filter(
        User.id == "usr-admin",
        User.workspace_id == workspace.id
    ).first()
    if not admin_user:
        email_in_use = db.query(User).filter(
            User.email == "pooja@apexstaffing.in"
        ).first()
        id_in_use = db.query(User).filter(User.id == "usr-admin").first()
        if not email_in_use and not id_in_use:
            db.add(User(
                id="usr-admin",
                workspace_id=workspace.id,
                email="pooja@apexstaffing.in",
                hashed_password="hashed_secure_password",
                full_name="Pooja Kulkarni (MIS Lead)",
                role=UserRole.MIS_EXECUTIVE
            ))

    for name, email in (
        ("Priya Sharma", "priya@apexstaffing.in"),
        ("Rahul Verma", "rahul@apexstaffing.in"),
        ("Amit Patel", "amit@apexstaffing.in"),
    ):
        existing_recruiter = db.query(RecruiterProfile).filter(
            RecruiterProfile.workspace_id == workspace.id,
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
                workspace_id=workspace.id,
                full_name=name,
                email=email,
                calendar_identifier=email
            ))

    db.flush()
    return workspace
