from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.enums import SourceType, SyncStatus, StandardField


class ColumnMappingItem(BaseModel):
    standard_field: StandardField
    source_column: Optional[str] = None
    confidence: float
    sample_values: List[str] = []
    is_confirmed: bool = False


class ColumnDetectionResponse(BaseModel):
    total_columns_found: int
    detected_mappings: Dict[str, ColumnMappingItem]


class ConfirmMappingRequest(BaseModel):
    data_source_id: str
    mappings: Dict[StandardField, str]  # standard_field -> confirmed source_column_name


class DataSourceCreate(BaseModel):
    recruiter_id: Optional[str] = None
    source_type: SourceType = SourceType.GOOGLE_SHEET
    name: str
    sheet_id_or_url: str
    sheet_tab_name: Optional[str] = None


class DataSourceResponse(BaseModel):
    id: str
    workspace_id: str
    recruiter_id: Optional[str]
    source_type: SourceType
    name: str
    sheet_id_or_url: str
    sheet_tab_name: Optional[str]
    sync_status: SyncStatus
    last_synced_at: Optional[datetime]
    last_error_message: Optional[str]

    class Config:
        from_attributes = True

