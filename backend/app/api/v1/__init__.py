"""API v1 router — aggregates all v1 sub-routers."""

from fastapi import APIRouter

from app.api.v1.account import router as account_router
from app.api.v1.admin import router as admin_router
from app.api.v1.analyses import router as analyses_router
from app.api.v1.coaching_sse import router as coaching_sse_router
from app.api.v1.exports import router as exports_router
from app.api.v1.insights import router as insights_router
from app.api.v1.profiles import router as profiles_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(profiles_router, prefix="/profiles")
api_v1_router.include_router(analyses_router, prefix="/analyses")
api_v1_router.include_router(coaching_sse_router, prefix="/analyses")
api_v1_router.include_router(exports_router, prefix="/analyses")
api_v1_router.include_router(insights_router, prefix="/insights")
api_v1_router.include_router(admin_router, prefix="/admin")
api_v1_router.include_router(account_router, prefix="/account")
