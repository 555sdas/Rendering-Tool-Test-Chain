from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.user import User
from app.services.audit_service import log_audit
from app.services.system_settings_service import SystemSettingsService


router = APIRouter(prefix="/system-settings", tags=["系统设置"])


class UnitySettingsUpdate(BaseModel):
    unity_executable_path: str = ""
    unity_project_path: str = ""
    unity_scene_path: str = ""
    collector_package_path: str = ""


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
