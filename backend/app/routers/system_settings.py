from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.scoring_definition_service import ScoringDefinitionValidationError
from app.services.system_settings_service import SystemSettingsService
router = APIRouter(prefix="/system-settings", tags=["系统设置"])


class UnitySettingsUpdate(BaseModel):
    unity_executable_path: str = ""
    unity_project_path: str = ""
    unity_scene_path: str = ""
    collector_package_path: str = ""


class TestScopePayload(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    source: str | None = None
    basic_metrics: dict[str, bool] = Field(default_factory=dict)
    quality_categories: dict[str, bool] = Field(default_factory=dict)
    quality_metrics: dict[str, bool] = Field(default_factory=dict)


class ScoringDefinitionPayload(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    category_weights: dict[str, float] = Field(default_factory=dict)


def _weights_audit_payload(definition: dict) -> dict[str, float]:
    weights = definition.get("category_weights") or {}
    return {key: float(weights.get(key, 0)) for key in ("lighting", "material", "post_processing", "physics")}


@router.get("/scoring-definition")
async def get_scoring_definition(
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    return SystemSettingsService().get_scoring_definition()


@router.put("/scoring-definition")
async def update_scoring_definition(
    request: Request,
    payload: ScoringDefinitionPayload,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    service = SystemSettingsService()
    before = service.get_scoring_definition()
    try:
        result = service.update_scoring_definition(payload.model_dump())
    except ScoringDefinitionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await log_audit(
        db=db,
        action="system_settings_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="scoring_definition",
        resource_id="category_weights",
        details={
            "before_weights": _weights_audit_payload(before["definition"]),
            "after_weights": _weights_audit_payload(result["definition"]),
        },
    )
    return result


@router.post("/scoring-definition/reset")
async def reset_scoring_definition(
    request: Request,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    service = SystemSettingsService()
    before = service.get_scoring_definition()
    result = service.reset_scoring_definition()
    await log_audit(
        db=db,
        action="system_settings_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="scoring_definition",
        resource_id="category_weights",
        details={
            "action": "reset_to_builtin_default",
            "before_weights": _weights_audit_payload(before["definition"]),
            "after_weights": _weights_audit_payload(result["definition"]),
        },
    )
    return result


@router.get("/test-metrics/catalog")
async def get_test_metrics_catalog(
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    return SystemSettingsService().get_test_metrics_catalog()


@router.get("/test-metrics")
async def get_default_test_metrics(
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    return SystemSettingsService().get_default_test_scope()


@router.put("/test-metrics")
async def update_default_test_metrics(
    request: Request,
    payload: TestScopePayload,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    service = SystemSettingsService()
    before = service.get_default_test_scope()
    result = service.update_default_test_scope(payload.model_dump())
    await log_audit(
        db=db,
        action="system_settings_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_metrics",
        resource_id="default_scope",
        details={
            "before_selected_count": before["scope_summary"]["selected_count"],
            "after_selected_count": result["scope_summary"]["selected_count"],
            "selected_labels": result["scope_summary"]["selected_labels"],
        },
    )
    return result


@router.post("/test-metrics/reset")
async def reset_default_test_metrics(
    request: Request,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    result = SystemSettingsService().reset_default_test_scope()
    await log_audit(
        db=db,
        action="system_settings_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_metrics",
        resource_id="default_scope",
        details={"action": "reset_to_builtin_default"},
    )
    return result


@router.get("/unity")
async def get_unity_settings(
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    return SystemSettingsService().get_unity_settings()


@router.put("/unity")
async def update_unity_settings(
    request: Request,
    payload: UnitySettingsUpdate,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    result = SystemSettingsService().update_unity_settings(payload.model_dump())
    await log_audit(
        db=db,
        action="system_settings_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="unity_settings",
        resource_id="unity",
        details={
            "unity_executable_path": payload.unity_executable_path,
            "unity_project_path": payload.unity_project_path,
            "unity_scene_path": payload.unity_scene_path,
            "collector_package_path": payload.collector_package_path,
        },
    )
    return result
