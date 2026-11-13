from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.models import (
    Workspace,
    User,
    UserRole,
    RecruiterProfile,
    StatusTaxonomy,
    DEFAULT_INDIAN_TAXONOMY_PRESETS,
    AuditLog,
    AuditAction,
)
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse
from app.schemas.recruiter import RecruiterCreate, RecruiterResponse

router = APIRouter(prefix="/workspaces", tags=["Workspaces & Onboarding"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)):
    """
    Onboards a new agency workspace:
    1. Creates the workspace tenant with IST timezone.
    2. Creates the Agency Owner user.
    3. Seeds 23 default Indian recruitment status taxonomy mappings.
    4. Logs workspace initialization audit event.
    """
    # Check if slug or email exists
    if db.query(Workspace).filter(Workspace.slug == payload.slug).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace slug '{payload.slug}' is already taken."
        )
    if db.query(User).filter(User.email == payload.admin_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{payload.admin_email}' is already registered."
        )

    # 1. Workspace
    workspace = Workspace(
        name=payload.name,
        slug=payload.slug,
        timezone=payload.timezone or settings.DEFAULT_TIMEZONE,
        service_account_email=settings.GOOGLE_SERVICE_ACCOUNT_EMAIL
    )
    db.add(workspace)
    db.flush()

    # 2. Agency Owner Admin User (Demo: store hash, bcrypt/argon2 in auth module)
    admin_user = User(
        workspace_id=workspace.id,
        email=payload.admin_email,
        full_name=payload.admin_name,
        hashed_password=f"hashed_{payload.admin_password}",
        role=UserRole.AGENCY_OWNER
    )
    db.add(admin_user)
    db.flush()

    # 3. Seed Default Indian Recruitment Taxonomy Presets
    for raw, category in DEFAULT_INDIAN_TAXONOMY_PRESETS:
        tax = StatusTaxonomy(
            workspace_id=workspace.id,
            raw_status=raw,
            category=category,
            is_default=True
        )
        db.add(tax)

    # 4. Audit Log
    audit = AuditLog(
        workspace_id=workspace.id,
        actor_user_id=admin_user.id,
        action=AuditAction.WORKSPACE_CREATED,
        details={"name": workspace.name, "slug": workspace.slug}
    )
    db.add(audit)

    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/default", response_model=WorkspaceResponse)
def get_default_workspace(db: Session = Depends(get_db)):
    """Returns the workspace provisioned for the local frontend."""
    workspace = db.query(Workspace).filter(
        Workspace.slug == "apex-staffing"
    ).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default workspace is not provisioned. Restart the backend to initialize it."
        )
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: str, db: Session = Depends(get_db)):
    """Retrieves workspace settings, including service account email."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


@router.post("/{workspace_id}/recruiters", response_model=RecruiterResponse, status_code=status.HTTP_201_CREATED)
def add_recruiter(workspace_id: str, payload: RecruiterCreate, db: Session = Depends(get_db)):
    """Adds a recruiter to the agency roster."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    recruiter = RecruiterProfile(
        workspace_id=workspace.id,
        full_name=payload.full_name,
        email=payload.email,
        calendar_identifier=payload.calendar_identifier or payload.email
    )
    db.add(recruiter)
    db.commit()
    db.refresh(recruiter)
    return recruiter


@router.get("/{workspace_id}/recruiters", response_model=List[RecruiterResponse])
def list_recruiters(workspace_id: str, db: Session = Depends(get_db)):
    """Lists all active recruiters in the agency."""
    return db.query(RecruiterProfile).filter(
        RecruiterProfile.workspace_id == workspace_id,
        RecruiterProfile.is_active == True
    ).all()
