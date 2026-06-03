from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.project import Project
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
    session: Optional[dict] = None
    uploadTime: Optional[datetime] = None
    sampleCount: Optional[int] = None


class PlatformSessionAutoCreate(BaseModel):
    project_id: int = Field(..., gt=0)
    scene_id: Optional[int] = None
    session_name_prefix: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    xr_runtime: Optional[str] = None
    app_version: Optional[str] = None
    config: Optional[dict] = None


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


def _first_value(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _try_parse_timestamp(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    return None


def _parse_timestamp(value) -> datetime:
    parsed = _try_parse_timestamp(value)
    if parsed:
        return parsed
    return datetime.utcnow()


def _parse_float(value) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _device_info_from_sample(item: dict) -> dict:
    device_info = item.get("deviceInfo") or item.get("device_info") or {}
    if not isinstance(device_info, dict):
        device_info = {}
    return device_info


def _merge_session_config(session: TestSession, updates: dict) -> None:
    config = dict(session.config or {})
    for key, value in updates.items():
        if value not in (None, ""):
            config[key] = value
    session.config = config


def _session_response(session: TestSession) -> dict:
    return {
        "id": session.id,
        "name": session.name,
        "description": session.description,
        "status": session.status.value if hasattr(session.status, "value") else session.status,
        "device_model": session.device_model,
        "os_version": session.os_version,
        "xr_runtime": session.xr_runtime,
        "app_version": session.app_version,
        "scene_id": session.scene_id,
        "user_id": session.user_id,
        "project_id": session.project_id,
        "config": session.config,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_seconds": session.duration_seconds,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def _platform_project_response(project: Project, db: Session) -> dict:
    session_count = (
        db.query(func.count(TestSession.id))
        .filter(TestSession.project_id == project.id)
        .scalar()
        or 0
    )
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "project_type": project.project_type,
        "status": project.status,
        "session_count": session_count,
        "next_session_index": session_count + 1,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.get("/platform/projects")
async def list_platform_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query("active", alias="status"),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    query = db.query(Project)
    if status_filter:
        query = query.filter(Project.status == status_filter)

    total = query.count()
    projects = query.order_by(desc(Project.created_at)).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [_platform_project_response(project, db) for project in projects],
    }


@router.post("/platform/test-sessions/auto-start")
async def auto_start_platform_test_session(
    request: Request,
    session_data: PlatformSessionAutoCreate,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == session_data.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    session_count = (
        db.query(func.count(TestSession.id))
        .filter(TestSession.project_id == project.id)
        .scalar()
        or 0
    )
    run_index = session_count + 1
    session_name = f"#{run_index}"

    config = dict(session_data.config or {})
    config.update(
        {
            "source": "unity_plugin",
            "platform_project_id": project.id,
            "platform_project_name": project.name,
            "run_index": run_index,
            "session_sequence": run_index,
        }
    )

    service = DataCollectionService(db)
    session = service.create_test_session(
        name=session_name,
        description=session_data.description or "Unity plugin auto-created session",
        device_model=session_data.device_model,
        os_version=session_data.os_version,
        xr_runtime=session_data.xr_runtime,
        app_version=session_data.app_version,
        scene_id=session_data.scene_id,
        user_id=current_user.id,
        project_id=project.id,
        config=config,
    )
    session.status = TestSessionStatus.RUNNING.value
    session.started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_session",
        resource_id=str(session.id),
        details={"action": "unity_auto_start", "project_id": project.id, "run_index": run_index},
    )

    response = _session_response(session)
    response.update(
        {
            "run_index": run_index,
            "project_name": project.name,
            "upload_url": f"/data-collection/test-sessions/{session.id}/samples/batch",
        }
    )
    return response


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
    return {"total": total, "items": [_session_response(session) for session in sessions]}


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
    return _session_response(session)


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

    db.refresh(session)
    return _session_response(session)


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

    return _session_response(session)


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

    return _session_response(session)


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
    timestamps: list[datetime] = []
    elapsed_seconds: list[float] = []
    first_device_info: dict = {}
    first_sample: dict = payload.samples[0] if payload.samples else {}
    for item in payload.samples:
        extra_metrics = item.get("extra_metrics") or item.get("extraMetrics") or {}
        if not isinstance(extra_metrics, dict):
            extra_metrics = {}

        render_quality = item.get("render_quality") or item.get("renderQuality")
        if isinstance(render_quality, dict):
            extra_metrics["render_quality"] = render_quality

        device_info = _device_info_from_sample(item)
        if device_info:
            extra_metrics["device_info"] = device_info
            if not first_device_info:
                first_device_info = device_info

        timestamp = _parse_timestamp(item.get("timestamp"))
        timestamps.append(timestamp)
        elapsed_time = _parse_float(
            item.get("elapsedTime")
            or item.get("elapsed_time")
            or item.get("elapsed_seconds")
        )
        if elapsed_time is not None:
            elapsed_seconds.append(max(0.0, elapsed_time))

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
    upload_session = payload.session or {}
    if not isinstance(upload_session, dict):
        upload_session = {}

    if timestamps:
        first_ts = min(timestamps)
        last_ts = max(timestamps)
        timestamp_duration = max(0.0, (last_ts - first_ts).total_seconds())
        session_duration = _parse_float(
            upload_session.get("duration")
            or upload_session.get("durationSeconds")
            or upload_session.get("duration_seconds")
        )
        elapsed_duration = max(elapsed_seconds) if elapsed_seconds else None
        duration_candidates = [
            value for value in [timestamp_duration, session_duration, elapsed_duration]
            if value is not None
        ]
        render_duration = max(duration_candidates) if duration_candidates else timestamp_duration
        session_start = _try_parse_timestamp(upload_session.get("startTime") or upload_session.get("start_time"))
        start_ts = session_start or session.started_at or first_ts
        end_ts = last_ts
        if render_duration is not None:
            duration_end_ts = start_ts + timedelta(seconds=render_duration)
            if duration_end_ts > end_ts:
                end_ts = duration_end_ts

        session.started_at = start_ts
        session.ended_at = end_ts
        session.duration_seconds = max(0.0, render_duration or (end_ts - start_ts).total_seconds())
        session.status = TestSessionStatus.COMPLETED.value

        _merge_session_config(
            session,
            {
                "render_duration_seconds": round(session.duration_seconds, 3),
                "sample_time_span_seconds": round(timestamp_duration, 3),
                "session_duration_seconds": round(session_duration, 3) if session_duration is not None else None,
                "max_sample_elapsed_seconds": round(elapsed_duration, 3) if elapsed_duration is not None else None,
            },
        )

    session.app_version = _first_value(
        session.app_version,
        upload_session.get("appVersion"),
        upload_session.get("productName"),
    )
    unity_version = upload_session.get("unityVersion")

    device_info = first_device_info
    if device_info:
        session.device_model = _first_value(
            session.device_model,
            device_info.get("deviceModel"),
            device_info.get("deviceName"),
            first_sample.get("xrDeviceName"),
        )
        session.os_version = _first_value(session.os_version, device_info.get("operatingSystem"))
        _merge_session_config(
            session,
            {
                "device_name": _first_value(device_info.get("deviceName"), device_info.get("deviceModel")),
                "device_model": device_info.get("deviceModel"),
                "os_version": device_info.get("operatingSystem"),
                "cpu_model": device_info.get("processorType"),
                "processor_count": device_info.get("processorCount"),
                "gpu_model": device_info.get("graphicsDeviceName"),
                "gpu_vendor": device_info.get("graphicsDeviceVendor"),
                "gpu_version": device_info.get("graphicsDeviceVersion"),
                "gpu_memory_mb": device_info.get("graphicsMemorySize"),
                "system_memory_mb": device_info.get("systemMemorySize"),
                "ram_gb": round(device_info.get("systemMemorySize", 0) / 1024, 2)
                if isinstance(device_info.get("systemMemorySize"), (int, float))
                else None,
                "screen_resolution": device_info.get("screenResolution") or first_sample.get("screenResolution"),
                "unity_version": unity_version,
                "xr_device_name": first_sample.get("xrDeviceName"),
                "sample_count": len(objects),
            },
        )
    else:
        _merge_session_config(session, {"sample_count": len(objects), "unity_version": unity_version})

    db.commit()

    db.refresh(session)
    return {
        "inserted": len(objects),
        "session_id": session_id,
        "status": session.status.value if hasattr(session.status, "value") else session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_seconds": session.duration_seconds,
    }


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
