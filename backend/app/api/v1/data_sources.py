from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import io
import pandas as pd

from app.core.database import get_db
from app.models import (
    DataSource,
    ColumnMapping,
    RecruiterProfile,
    SyncStatus,
    StandardField,
    AuditLog,
    AuditAction,
)
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceResponse,
    ColumnDetectionResponse,
    ColumnMappingItem,
    ConfirmMappingRequest,
)
from app.services.column_detector import ColumnDetector

router = APIRouter(prefix="/data-sources", tags=["Data Sources & Column Mapping"])


@router.post("/{workspace_id}", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
def create_data_source(workspace_id: str, payload: DataSourceCreate, db: Session = Depends(get_db)):
    """Registers a spreadsheet or file data source for an agency or recruiter."""
    ds = DataSource(
        workspace_id=workspace_id,
        recruiter_id=payload.recruiter_id,
        source_type=payload.source_type,
        name=payload.name,
        sheet_id_or_url=payload.sheet_id_or_url,
        sheet_tab_name=payload.sheet_tab_name,
        sync_status=SyncStatus.PENDING_MAPPING
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.post("/detect-from-file", response_model=ColumnDetectionResponse)
async def detect_columns_from_file(file: UploadFile = File(...)):
    """
    Analyzes an uploaded Excel (.xlsx) or CSV file and suggests standardized column mappings
    with confidence scores and sample values.
    """
    content = await file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Please upload .csv or .xlsx."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse spreadsheet: {str(e)}"
        )

    detections = ColumnDetector.analyze_dataframe(df)

    formatted_mappings = {}
    for standard_field, item in detections.items():
        formatted_mappings[standard_field.value] = ColumnMappingItem(
            standard_field=standard_field,
            source_column=item["source_column"],
            confidence=item["confidence"],
            sample_values=item["sample_values"],
            is_confirmed=item["auto_confirmed"]
        )

    return ColumnDetectionResponse(
        total_columns_found=len(df.columns),
        detected_mappings=formatted_mappings
    )


@router.post("/confirm-mappings")
def confirm_mappings(payload: ConfirmMappingRequest, db: Session = Depends(get_db)):
    """
    Saves and confirms the column mapping for a specific data source.
    Transitions data source status to ACTIVE.
    """
    ds = db.query(DataSource).filter(DataSource.id == payload.data_source_id).first()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found.")

    # Remove existing mappings if re-confirming
    db.query(ColumnMapping).filter(ColumnMapping.data_source_id == ds.id).delete()

    for standard_field, source_col in payload.mappings.items():
        mapping = ColumnMapping(
            data_source_id=ds.id,
            standard_field=standard_field,
            source_column_name=source_col,
            confidence_score=1.0,
            is_confirmed=True
        )
        db.add(mapping)

    ds.sync_status = SyncStatus.ACTIVE
    db.commit()

    return {"message": "Column mappings confirmed successfully.", "status": ds.sync_status}

