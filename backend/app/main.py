import asyncio
import logging
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.auth import configured_auth_accounts, validate_production_settings
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.api.v1.router import api_router
from app.models import DataSource, SyncStatus, User, Workspace
from app.services.sync_coordinator import SyncCoordinator
from app.services.workspace_bootstrap import ensure_default_workspace

validate_production_settings()

# Create tables on startup
Base.metadata.create_all(bind=engine)
logger = logging.getLogger(__name__)
sheet_sync_task: asyncio.Task | None = None

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Recruitment MIS Automation & Productivity Intelligence",
    docs_url=None if settings.APP_ENV.lower() == "production" else "/docs",
    redoc_url=None if settings.APP_ENV.lower() == "production" else "/redoc",
    openapi_url=None if settings.APP_ENV.lower() == "production" else "/openapi.json"
)

# Exception handler to safely handle any validation errors containing raw binary input
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = []
    for err in exc.errors():
        safe_err = dict(err)
        if "input" in safe_err and isinstance(safe_err["input"], (bytes, bytearray)):
            safe_err["input"] = f"<binary upload: {len(safe_err['input'])} bytes>"
        safe_errors.append(safe_err)
    return JSONResponse(status_code=422, content={"detail": safe_errors})

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.middleware("http")
async def require_authenticated_api_user(request: Request, call_next):
    if settings.APP_ENV.lower() != "production" or not request.url.path.startswith(f"{settings.API_V1_STR}/"):
        return await call_next(request)

    public_auth_paths = {
        f"{settings.API_V1_STR}/auth/status",
        f"{settings.API_V1_STR}/auth/login",
        f"{settings.API_V1_STR}/auth/logout",
    }
    if request.url.path in public_auth_paths:
        return await call_next(request)

    from app.api.v1.auth import current_session_user

    db = SessionLocal()
    try:
        user = current_session_user(request, db)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Sign in to access RecruiterPulse."})
        request.state.authenticated_user_id = user.id
    finally:
        db.close()
    return await call_next(request)


async def sync_registered_workspaces():
    while True:
        db = SessionLocal()
        try:
            workspace_ids = [
                workspace_id
                for (workspace_id,) in db.query(Workspace.id).join(
                    DataSource,
                    DataSource.workspace_id == Workspace.id
                ).filter(
                    DataSource.sync_status == SyncStatus.ACTIVE
                ).distinct().all()
            ]
        except Exception:
            logger.exception("Unable to find workspaces with active Google Sheets.")
            workspace_ids = []
        finally:
            db.close()

        for workspace_id in workspace_ids:
            db = SessionLocal()
            try:
                await SyncCoordinator.run_workspace_sync(workspace_id, db)
            except Exception:
                logger.exception("Scheduled Google Sheets sync failed for workspace %s.", workspace_id)
                db.rollback()
            finally:
                db.close()

        await asyncio.sleep(settings.GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES * 60)


@app.on_event("startup")
async def provision_default_workspace():
    global sheet_sync_task
    if settings.GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES < 1:
        raise ValueError("GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES must be at least 1.")
    db = SessionLocal()
    try:
        workspace = ensure_default_workspace(db)
        if settings.APP_ENV.lower() == "production":
            for account in configured_auth_accounts():
                email = account.email.strip().lower()
                user = db.query(User).filter(User.email == email).first()
                if user and user.workspace_id != workspace.id:
                    raise ValueError(f"Configured sign-in account {email} belongs to another workspace.")
                if not user:
                    user = User(
                        workspace_id=workspace.id,
                        email=email,
                        full_name=account.full_name.strip(),
                        role=account.role,
                        hashed_password=account.password_hash
                    )
                    db.add(user)
                else:
                    user.full_name = account.full_name.strip()
                    user.role = account.role
                    user.hashed_password = account.password_hash
                    user.is_active = True
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    sheet_sync_task = asyncio.create_task(sync_registered_workspaces())


@app.on_event("shutdown")
async def stop_scheduled_sheet_sync():
    if sheet_sync_task:
        sheet_sync_task.cancel()
        try:
            await sheet_sync_task
        except asyncio.CancelledError:
            pass


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "version": settings.VERSION}


# Mount built frontend static files if dist folder exists
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
