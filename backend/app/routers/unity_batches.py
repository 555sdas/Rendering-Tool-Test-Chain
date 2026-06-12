from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.unity_batch_service import UnityBatchService


router = APIRouter(prefix="/unity-runner/test-batches", tags=["Unity 多场景编排"])


class BatchSceneStartRequest(BaseModel):
    scene_resource_id: str = Field(..., min_length=1)
    test_scope: dict[str, Any] | None = None
    collect_interval: float = Field(1.0, ge=0.1, le=10.0)
    frame_rate_duration_seconds: float = Field(30.0, ge=1.0, le=600.0)
    metrics_duration_seconds: float = Field(30.0, ge=1.0, le=600.0)


class UnityBatchStartRequest(BaseModel):
    project_id: int = Field(..., gt=0)
    unity_engine_id: str = Field(..., min_length=1)
    batchmode: bool = False
    ensure_plugin: bool = True
    scenes: list[BatchSceneStartRequest] = Field(..., min_length=2, max_length=20)


class UnityBatchDecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(retry|skip|abort)$")
    expected_item_id: int = Field(..., gt=0)
    expected_scene_index: int = Field(..., ge=0)
    decision_version: int = Field(..., ge=0)


@router.get("")
async def list_test_batches(
    project_id: int | None = Query(None, gt=0),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    return UnityBatchService(db).list_batches(
        project_id=project_id,
        status_filter=status,
        skip=skip,
        limit=limit,
    )


@router.get("/active")
async def get_active_test_batch(
    project_id: int = Query(..., gt=0),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    batch = UnityBatchService(db).get_active_batch_for_project(project_id)
    return {"item": batch}


@router.get("/{batch_id}")
async def get_test_batch(
    batch_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    return UnityBatchService(db).get_batch(batch_id)


@router.post("/start")
async def start_test_batch(
    request: Request,
    payload: UnityBatchStartRequest,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = UnityBatchService(db)
    result = service.start_batch(
        project_id=payload.project_id,
        unity_engine_id=payload.unity_engine_id,
        scenes=[scene.model_dump() for scene in payload.scenes],
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
        resource_type="test_batch",
        resource_id=str(result["batch"]["id"]),
        details={
            "source": "web_unity_batch",
            "project_id": payload.project_id,
            "parent_task_id": result["batch"]["parent_task_id"],
            "scene_total": result["batch"]["scene_total"],
        },
    )

    return result


@router.post("/{batch_id}/decision")
async def apply_batch_decision(
    request: Request,
    batch_id: int,
    payload: UnityBatchDecisionRequest,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    service = UnityBatchService(db)
    result = service.apply_decision(
        batch_id=batch_id,
        action=payload.action,
        expected_item_id=payload.expected_item_id,
        expected_scene_index=payload.expected_scene_index,
        decision_version=payload.decision_version,
    )

    await log_audit(
        db=db,
        action="test_execute",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_batch",
        resource_id=str(batch_id),
        details={
            "source": "web_unity_batch_decision",
            "action": payload.action,
            "expected_item_id": payload.expected_item_id,
            "expected_scene_index": payload.expected_scene_index,
        },
    )
    return result


@router.post("/{batch_id}/stop")
async def stop_test_batch(
    request: Request,
    batch_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
    db: Session = Depends(get_db),
):
    result = UnityBatchService(db).stop_batch(batch_id)

    await log_audit(
        db=db,
        action="test_stop",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_batch",
        resource_id=str(batch_id),
        details={"source": "web_unity_batch_stop"},
    )

    return result
