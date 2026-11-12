from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.sync_coordinator import SyncCoordinator
from app.api.v1.reports import serialize_report
from app.schemas.report import HourlyReportResponse

router = APIRouter(prefix="/sync", tags=["Live Sync & Orchestration"])


@router.post("/{workspace_id}", response_model=HourlyReportResponse, status_code=status.HTTP_200_OK)
async def trigger_workspace_sync(workspace_id: str, db: Session = Depends(get_db)):
    """
    Triggers on-demand or scheduled live synchronization:
    1. Fetches recruiter Google Sheets
    2. Calculates calling metrics
    3. Retrieves tomorrow's calendar interviews with 4-tier attribution
    4. Generates/updates the cumulative DRAFT_PENDING_APPROVAL report for the current slot.
    """
    try:
        report = await SyncCoordinator.run_workspace_sync(workspace_id=workspace_id, db=db)
        return serialize_report(report)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync execution failed: {str(e)}"
        )

