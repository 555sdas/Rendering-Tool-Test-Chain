from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.test_session import TestSession, TestSessionStatus
from app.models.test_task import TestTask, TestTaskStatus
from app.models.performance_sample import PerformanceSample
from app.core.permissions import Permission, require_permission, get_current_user
from app.services.data_collection_service import DataCollectionService
from app.services.audit_service import log_audit

router = APIRouter(prefix="/data-collection", tags=["数据采集"])


class TestSessionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    xr_runtime: Optional[str] = None
    app_version: Optional[str] = None
    scene_id: Optional[int] = None
    project_id: Optional[int] = None
    config: Optional[dict] = None


class TestSessionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TestSessionStatus] = None


class PerformanceSampleCreate(BaseModel):
    timestamp: datetime
    frame_time_ms: Optional[float] = None
    fps: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    gpu_usage_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    battery_level: Optional[float] = None
    battery_temperature: Optional[float] = None
    draw_calls: Optional[int] = None
    triangle_count: Optional[int] = None
    vertex_count: Optional[int] = None
    set_pass_calls: Optional[int] = None
    texture_memory_mb: Optional[float] = None
    mesh_memory_mb: Optional[float] = None
    render_texture_memory_mb: Optional[float] = None
    gc_collect_count: Optional[int] = None
    gc_allocated_mb: Optional[float] = None
    screen_resolution: Optional[str] = None
    tracking_state: Optional[str] = None
    prediction_error_ms: Optional[float] = None
    pose_latency_ms: Optional[float] = None
    extra_metrics: Optional[dict] = None


class PerformanceSampleBatchCreate(BaseModel):
    samples: list[dict] = Field(..., min_length=1)


class TestTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    task_type: str = Field(..., min_length=1, max_length=50)
    project_id: Optional[int] = None
    scene_id: Optional[int] = None
    config: Optional[dict] = None
    target_devices: Optional[list] = None
    priority: int = Field(0, ge=0, le=10)
    scheduled_at: Optional[datetime] = None


class TestTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TestTaskStatus] = None
    priority: Optional[int] = Field(None, ge=0, le=10)


@router.get("/test-sessions")
async def list_test_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[TestSessionStatus] = None,
    project_id: Optional[int] = None,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    query = db.query(TestSession)
    if status:
        query = query.filter(TestSession.status == status.value)
    if project_id:
        query = query.filter(TestSession.project_id == project_id)

    total = query.count()
    sessions = query.order_by(desc(TestSession.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "items": sessions}


@router.get("/test-sessions/{session_id}")
async def get_test_session(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试会话不存在",
        )
    return session


@router.post("/test-sessions")
async def create_test_session(
    request: Request,
    session_data: TestSessionCreate,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    session = service.create_test_session(
        name=session_data.name,
        description=session_data.description,
        device_model=session_data.device_model,
        os_version=session_data.os_version,
        xr_runtime=session_data.xr_runtime,
        app_version=session_data.app_version,
        scene_id=session_data.scene_id,
        user_id=current_user.id,
        project_id=session_data.project_id,
        config=session_data.config,
    )

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_session",
        resource_id=str(session.id),
        details={"name": session_data.name},
    )

    return session


@router.post("/test-sessions/{session_id}/start")
async def start_test_session(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    session = service.start_test_session(session_id)

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_session",
        resource_id=str(session_id),
        details={"action": "start"},
    )

    return session


@router.post("/test-sessions/{session_id}/stop")
async def stop_test_session(
    request: Request,
    session_id: int,
    status: TestSessionStatus = TestSessionStatus.COMPLETED,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    session = service.stop_test_session(session_id, status)

    await log_audit(
        db=db,
        action="test_stop",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_session",
        resource_id=str(session_id),
        details={"action": "stop", "status": status.value},
    )

    return session


@router.post("/test-sessions/{session_id}/samples")
async def add_performance_sample(
    request: Request,
    session_id: int,
    sample_data: PerformanceSampleCreate,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试会话不存在",
        )

    service = DataCollectionService(db)
    sample = service.add_performance_sample(
        test_session_id=session_id,
        timestamp=sample_data.timestamp,
        frame_time_ms=sample_data.frame_time_ms,
        fps=sample_data.fps,
        cpu_usage_percent=sample_data.cpu_usage_percent,
        gpu_usage_percent=sample_data.gpu_usage_percent,
        memory_mb=sample_data.memory_mb,
        battery_level=sample_data.battery_level,
        battery_temperature=sample_data.battery_temperature,
        draw_calls=sample_data.draw_calls,
        triangle_count=sample_data.triangle_count,
        vertex_count=sample_data.vertex_count,
        set_pass_calls=sample_data.set_pass_calls,
        texture_memory_mb=sample_data.texture_memory_mb,
        mesh_memory_mb=sample_data.mesh_memory_mb,
        render_texture_memory_mb=sample_data.render_texture_memory_mb,
        gc_collect_count=sample_data.gc_collect_count,
        gc_allocated_mb=sample_data.gc_allocated_mb,
        screen_resolution=sample_data.screen_resolution,
        tracking_state=sample_data.tracking_state,
        prediction_error_ms=sample_data.prediction_error_ms,
        pose_latency_ms=sample_data.pose_latency_ms,
        extra_metrics=sample_data.extra_metrics,
    )

    return sample


@router.post("/test-sessions/{session_id}/samples/batch")
async def add_performance_samples_batch(
    session_id: int,
    payload: PerformanceSampleBatchCreate,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试会话不存在",
        )

    objects = []
    for item in payload.samples:
        extra_metrics = item.get("extra_metrics") or item.get("extraMetrics") or {}
        if not isinstance(extra_metrics, dict):
            extra_metrics = {}

        render_quality = item.get("render_quality") or item.get("renderQuality")
        if isinstance(render_quality, dict):
            extra_metrics["render_quality"] = render_quality

        timestamp = item.get("timestamp") or datetime.utcnow()
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        objects.append(
            PerformanceSample(
                test_session_id=session_id,
                timestamp=timestamp,
                frame_time_ms=item.get("frame_time_ms") or item.get("frameTimeMs"),
                fps=item.get("fps") or item.get("frameRate"),
                cpu_usage_percent=item.get("cpu_usage_percent") or item.get("cpuUsagePercent"),
                gpu_usage_percent=item.get("gpu_usage_percent") or item.get("gpuUsagePercent"),
                memory_mb=item.get("memory_mb") or item.get("totalMemoryMB"),
                battery_level=item.get("battery_level") or item.get("batteryLevel"),
                battery_temperature=item.get("battery_temperature") or item.get("batteryTemperature"),
                draw_calls=item.get("draw_calls") or item.get("drawCalls"),
                triangle_count=item.get("triangle_count") or item.get("triangles"),
                vertex_count=item.get("vertex_count") or item.get("vertices"),
                set_pass_calls=item.get("set_pass_calls") or item.get("setPassCalls"),
                texture_memory_mb=item.get("texture_memory_mb") or item.get("textureMemoryMB"),
                mesh_memory_mb=item.get("mesh_memory_mb") or item.get("meshMemoryMB"),
                render_texture_memory_mb=item.get("render_texture_memory_mb") or item.get("renderTextureMemoryMB"),
                gc_collect_count=item.get("gc_collect_count") or item.get("gcCollectCount"),
                gc_allocated_mb=item.get("gc_allocated_mb") or item.get("gcAllocatedMB"),
                screen_resolution=item.get("screen_resolution") or item.get("screenResolution"),
                tracking_state=item.get("tracking_state") or item.get("trackingState"),
                prediction_error_ms=item.get("prediction_error_ms") or item.get("predictionErrorMs"),
                pose_latency_ms=item.get("pose_latency_ms") or item.get("poseLatencyMs"),
                extra_metrics=extra_metrics or None,
            )
        )

    db.bulk_save_objects(objects)
    db.commit()

    return {"inserted": len(objects), "session_id": session_id}


@router.get("/test-sessions/{session_id}/samples")
async def get_session_samples(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    samples = service.get_test_session_samples(session_id, skip, limit)
    return samples


@router.get("/test-sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    stats = service.get_session_statistics(session_id)
    return stats


@router.get("/test-tasks")
async def list_test_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[TestTaskStatus] = None,
    project_id: Optional[int] = None,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    query = db.query(TestTask)
    if status:
        query = query.filter(TestTask.status == status.value)
    if project_id:
        query = query.filter(TestTask.project_id == project_id)

    total = query.count()
    tasks = query.order_by(desc(TestTask.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "items": tasks}


@router.post("/test-tasks")
async def create_test_task(
    request: Request,
    task_data: TestTaskCreate,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    task = service.create_test_task(
        name=task_data.name,
        task_type=task_data.task_type,
        creator_id=current_user.id,
        project_id=task_data.project_id,
        scene_id=task_data.scene_id,
        config=task_data.config,
        target_devices=task_data.target_devices,
        priority=task_data.priority,
        description=task_data.description,
        scheduled_at=task_data.scheduled_at,
    )

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_task",
        resource_id=str(task.id),
        details={"name": task_data.name, "type": task_data.task_type},
    )

    return task


@router.put("/test-tasks/{task_id}/status")
async def update_test_task_status(
    request: Request,
    task_id: int,
    status: TestTaskStatus,
    error_message: Optional[str] = None,
    result_summary: Optional[dict] = None,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = DataCollectionService(db)
    task = service.update_test_task_status(task_id, status, error_message, result_summary)

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_task",
        resource_id=str(task_id),
        details={"status": status.value},
    )

    return task
