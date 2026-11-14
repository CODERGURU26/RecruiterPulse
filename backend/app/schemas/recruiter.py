from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class RecruiterCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    calendar_identifier: Optional[str] = None


class RecruiterCalendarUpdate(BaseModel):
    calendar_identifier: Optional[str] = None


class RecruiterResponse(BaseModel):
    id: str
    workspace_id: str
    full_name: str
    email: Optional[str]
    calendar_identifier: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
