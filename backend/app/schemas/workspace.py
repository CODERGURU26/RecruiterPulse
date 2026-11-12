from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.enums import UserRole, SubscriptionTier


class WorkspaceCreate(BaseModel):
    name: str
    slug: str
    admin_name: str
    admin_email: str
    admin_password: str
    timezone: Optional[str] = "Asia/Kolkata"


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    timezone: str
    service_account_email: Optional[str]
    subscription_tier: SubscriptionTier
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: str
    workspace_id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True

