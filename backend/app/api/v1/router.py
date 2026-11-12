from fastapi import APIRouter
from app.api.v1.workspaces import router as workspaces_router
from app.api.v1.data_sources import router as data_sources_router
from app.api.v1.reports import router as reports_router
from app.api.v1.sync import router as sync_router

api_router = APIRouter()
api_router.include_router(workspaces_router)
api_router.include_router(data_sources_router)
api_router.include_router(reports_router)
api_router.include_router(sync_router)


