import asyncio
import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.api.v1.router import api_router
from app.models import DataSource, SyncStatus, Workspace
from app.services.sync_coordinator import SyncCoordinator
from app.services.workspace_bootstrap import ensure_default_workspace

# Create tables on startup
Base.metadata.create_all(bind=engine)
logger = logging.getLogger(__name__)
sheet_sync_task: asyncio.Task | None = None

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Recruitment MIS Automation & Productivity Intelligence"
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

# CORS Middleware (Allows frontend Next.js/Vite dev servers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


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
    db = SessionLocal()
    try:
        ensure_default_workspace(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if settings.GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES < 1:
        raise ValueError("GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES must be at least 1.")
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
