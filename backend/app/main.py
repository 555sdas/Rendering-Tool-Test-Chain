from fastapi import FastAPI
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.core.middleware import setup_cors, setup_security_headers, setup_request_logging
from app.routers import (
    auth_router,
    users_router,
    projects_router,
    scene_assets_router,
    data_collection_router,
    performance_analysis_router,
    test_reports_router,
    exports_router,
    audit_logs_router,
    cloud_ar_router,
    unity_runner_router,
    system_settings_router,
    progress_ws_router,
    unity_batches_router,
)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="XR Test Platform API - 用于XR应用性能测试与分析的后端服务",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

setup_cors(app)
setup_security_headers(app)
setup_request_logging(app)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(projects_router, prefix=settings.API_V1_PREFIX)
app.include_router(scene_assets_router, prefix=settings.API_V1_PREFIX)
app.include_router(data_collection_router, prefix=settings.API_V1_PREFIX)
app.include_router(performance_analysis_router, prefix=settings.API_V1_PREFIX)
app.include_router(test_reports_router, prefix=settings.API_V1_PREFIX)
app.include_router(exports_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_logs_router, prefix=settings.API_V1_PREFIX)
app.include_router(cloud_ar_router, prefix=settings.API_V1_PREFIX)
app.include_router(unity_runner_router, prefix=settings.API_V1_PREFIX)
app.include_router(system_settings_router, prefix=settings.API_V1_PREFIX)
app.include_router(progress_ws_router, prefix=settings.API_V1_PREFIX)
app.include_router(unity_batches_router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_event():
    init_db()
    db = SessionLocal()
    try:
        from app.services.unity_batch_service import UnityBatchService

        UnityBatchService(db).reconcile_active_batches()
    finally:
        db.close()


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
