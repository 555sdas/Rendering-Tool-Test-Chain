from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.unity_runner_service import UnityRunnerService


router = APIRouter(prefix="/unity-runner", tags=["Unity 本地测试"])


class QualityChecks(BaseModel):
    lighting: bool = True
    materials: bool = True
    post_processing: bool = True
    physics: bool = True


class MetricChecks(BaseModel):
    frame_rate: bool = True
    frame_time: bool = True
    cpu: bool = True
    gpu: bool = True
    memory: bool = True
    device_info: bool = True


class TestScopeRequest(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    source: str | None = None
    basic_metrics: dict[str, bool] = Field(default_factory=dict)
    quality_categories: dict[str, bool] = Field(default_factory=dict)
    quality_metrics: dict[str, bool] = Field(default_factory=dict)


class UnityTestStartRequest(BaseModel):
    project_id: int = Field(..., gt=0)
    unity_engine_id: str = Field(..., min_length=1)
    scene_resource_id: str = Field(..., min_length=1)
    test_scope: TestScopeRequest | None = None
    quality_checks: QualityChecks = Field(default_factory=QualityChecks)
    quality_metric_checks: dict[str, bool] = Field(default_factory=dict)
    metric_checks: MetricChecks = Field(default_factory=MetricChecks)
    collect_interval: float = Field(1.0, ge=0.1, le=10.0)
    frame_rate_duration_seconds: float = Field(30.0, ge=1.0, le=600.0)
    metrics_duration_seconds: float = Field(30.0, ge=1.0, le=600.0)
    batchmode: bool = False
    ensure_plugin: bool = True


@router.get("/test-metrics/catalog")
async def get_test_metrics_catalog(
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    return UnityRunnerService(db).get_test_metrics_catalog()


@router.get("/test-metrics/default-scope")
async def get_default_test_scope_for_run(
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    scope = UnityRunnerService(db).get_default_test_scope_for_run()
    from app.services.test_scope_service import TestScopeService

    return {
        "default_scope": scope,
        "scope_summary": TestScopeService.build_scope_summary(scope),
    }


@router.get("/engines")
async def list_unity_engines(
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = UnityRunnerService(db)
    return {"items": service.list_engines()}


@router.get("/scenes")
async def list_unity_scene_resources(
    project_id: Optional[int] = Query(None, gt=0),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = UnityRunnerService(db)
    return {"items": service.list_scenes(project_id=project_id)}


@router.post("/test-tasks/start")
async def start_unity_test_task(
    request: Request,
    payload: UnityTestStartRequest,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = UnityRunnerService(db)
    result = service.start_test(
        project_id=payload.project_id,
        unity_engine_id=payload.unity_engine_id,
        scene_resource_id=payload.scene_resource_id,
        test_scope=payload.test_scope.model_dump() if payload.test_scope else None,
        quality_checks=payload.quality_checks.model_dump(),
        quality_metric_checks=payload.quality_metric_checks,
        metric_checks=payload.metric_checks.model_dump(),
        collect_interval=payload.collect_interval,
        frame_rate_duration_seconds=payload.frame_rate_duration_seconds,
        metrics_duration_seconds=payload.metrics_duration_seconds,
        batchmode=payload.batchmode,
        ensure_plugin=payload.ensure_plugin,
        creator_id=current_user.id,
    )

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_task",
        resource_id=str(result["task"]["id"]),
        details={
            "source": "web_unity_runner",
            "project_id": payload.project_id,
            "session_id": result["session"]["id"],
            "unity_engine_id": payload.unity_engine_id,
            "scene_resource_id": payload.scene_resource_id,
        },
    )

    return result


@router.post("/test-tasks/{task_id}/stop")
async def stop_unity_test_task(
    request: Request,
    task_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = UnityRunnerService(db)
    result = service.stop_test(task_id)

    await log_audit(
        db=db,
        action="test_stop",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_task",
        resource_id=str(task_id),
        details={"source": "web_unity_runner"},
    )

    return result


@router.get("/test-tasks/{task_id}/logs")
async def get_unity_test_task_logs(
    task_id: int,
    tail_lines: int = Query(400, ge=20, le=1000),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = UnityRunnerService(db)
    return service.get_task_logs(task_id, tail_lines=tail_lines)
