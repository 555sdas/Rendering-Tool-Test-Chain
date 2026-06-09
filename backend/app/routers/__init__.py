from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.projects import router as projects_router
from app.routers.scene_assets import router as scene_assets_router
from app.routers.data_collection import router as data_collection_router
from app.routers.performance_analysis import router as performance_analysis_router
from app.routers.test_reports import router as test_reports_router
from app.routers.exports import router as exports_router
from app.routers.audit_logs import router as audit_logs_router
from app.routers.cloud_ar import router as cloud_ar_router
from app.routers.unity_runner import router as unity_runner_router

__all__ = [
    "auth_router",
    "users_router",
    "projects_router",
    "scene_assets_router",
    "data_collection_router",
    "performance_analysis_router",
    "test_reports_router",
    "exports_router",
    "audit_logs_router",
    "cloud_ar_router",
    "unity_runner_router",
]
