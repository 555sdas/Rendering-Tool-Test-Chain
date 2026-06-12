"""Real-time Unity test progress ingress and WebSocket fan-out."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.permissions import Permission, require_permission
from app.core.security import decode_token
from app.database import get_db
from app.models.test_task import TestTask
from app.models.user import User
from app.services.test_scope_service import TestScopeService
from app.services.unity_runner_service import UnityRunnerService


router = APIRouter(prefix="/unity-runner/progress", tags=["Unity 实时进度"])
_progress_connections: dict[int, list[WebSocket]] = {}
_latest_progress: dict[int, dict[str, Any]] = {}


class UnityProgressUpdate(BaseModel):
    task_id: int = Field(..., gt=0)
    session_id: int = Field(..., gt=0)
    phase: str
    phase_label: str
    progress: float = Field(..., ge=0, le=1)
    remaining_seconds: float = Field(..., ge=0)
    sample_count: int = Field(..., ge=0)
    fps: float = 0
    frame_time_ms: float = 0
    raw_frame_time_ms: float = 0
    cpu_usage_percent: float = 0
    gpu_usage_percent: float = 0
    memory_mb: float = 0
    managed_memory_mb: float = 0
    graphics_memory_mb: float = 0
    system_memory_mb: float = 0
    draw_calls: int = 0
    triangles: int = 0
    vertices: int = 0
    active_light_count: int = 0
    realtime_light_count: int = 0
    shadow_caster_count: int = 0
    reflection_probe_count: int = 0
    material_count: int = 0
    unique_material_count: int = 0
    transparent_material_count: int = 0
    post_process_volume_count: int = 0
    render_texture_count: int = 0
    rigidbody_count: int = 0
    collider_count: int = 0
    is_xr_active: bool = False
    xr_device_name: str = ""
    device_model: str = ""
    operating_system: str = ""
    unity_version: str = ""
    graphics_device_name: str = ""
    render_pipeline: str = ""
    screen_resolution: str = ""


async def broadcast(task_id: int, data: dict[str, Any]) -> None:
    _latest_progress[task_id] = data
    connections = _progress_connections.get(task_id, [])
    dead: list[WebSocket] = []
    for websocket in connections:
        try:
            await websocket.send_json(data)
        except Exception:
            dead.append(websocket)
    for websocket in dead:
        connections.remove(websocket)


@router.post("/{task_id}")
async def receive_progress(
    task_id: int,
    payload: UnityProgressUpdate,
    x_device_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if x_device_token != get_settings().DEVICE_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的设备采集令牌")
    if payload.task_id != task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务 ID 不匹配")

    data = payload.model_dump()
    data["type"] = "unity_progress"
    data["received_at"] = datetime.utcnow().isoformat() + "Z"
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if task and isinstance(task.config, dict):
        scope = TestScopeService.infer_scope_from_session_config(task.config)
        summary = task.config.get("test_scope_summary") or TestScopeService.build_scope_summary(scope)
        data["test_scope_version"] = scope.get("schema_version", 1)
        data["test_scope_summary"] = summary
        data["selected_metric_ids"] = summary.get("selected_ids", [])
        data["skipped_metric_ids"] = summary.get("skipped_ids", [])
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unity 测试任务不存在")
    summary = dict(task.result_summary or {})
    summary["latest_progress"] = data
    task.result_summary = summary
    UnityRunnerService(db).append_progress_event_log(task, data)
    db.commit()
    await broadcast(task_id, data)
    return {"ok": True}


@router.get("/{task_id}/latest")
async def get_latest_progress(
    task_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unity 测试任务不存在")
    latest = _latest_progress.get(task_id) or dict(task.result_summary or {}).get("latest_progress")
    return {"item": latest}


@router.websocket("/{task_id}/ws")
async def progress_websocket(websocket: WebSocket, task_id: int, token: str = Query("")):
    if not decode_token(token):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connections = _progress_connections.setdefault(task_id, [])
    connections.append(websocket)
    if task_id in _latest_progress:
        await websocket.send_json(_latest_progress[task_id])

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connections:
            connections.remove(websocket)
