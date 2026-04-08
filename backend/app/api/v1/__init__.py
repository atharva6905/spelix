"""API v1 router — aggregates all v1 sub-routers."""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.analyses import router as analyses_router
from app.api.v1.profiles import router as profiles_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(profiles_router, prefix="/profiles")
api_v1_router.include_router(analyses_router, prefix="/analyses")
api_v1_router.include_router(admin_router, prefix="/admin")
