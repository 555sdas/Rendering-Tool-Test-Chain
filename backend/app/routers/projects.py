from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.project import Project, ProjectStatus, ProjectType
from app.models.test_session import TestSession
from app.services.unity_runner_service import UnityRunnerService
from app.core.permissions import Permission, require_permission, get_current_user
from app.services.audit_service import log_audit
from app.utils.datetime import isoformat_utc

router = APIRouter(prefix="/projects", tags=["项目管理"])


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    project_type: str = Field(default=ProjectType.RENDER_PERFORMANCE.value)
    status: str = Field(default=ProjectStatus.ACTIVE.value)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    project_type: str
    status: str
    created_by: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


def _session_response(session: TestSession) -> dict:
    from app.utils.session_display import get_session_scene_display_name

    scene_asset_name = session.scene.name if getattr(session, "scene", None) is not None else None
    scene_display_name = get_session_scene_display_name(
        config=session.config,
        scene_id=session.scene_id,
        scene_asset_name=scene_asset_name,
    )
    return {
        "id": session.id,
        "name": session.name,
        "scene_display_name": scene_display_name,
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
        "started_at": isoformat_utc(session.started_at),
        "ended_at": isoformat_utc(session.ended_at),
        "duration_seconds": session.duration_seconds,
        "created_at": isoformat_utc(session.created_at),
        "updated_at": isoformat_utc(session.updated_at),
    }


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Project)
    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))
    if status:
        query = query.filter(Project.status == status)

    projects = query.order_by(desc(Project.created_at)).offset(skip).limit(limit).all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )
    return project


@router.get("/{project_id}/test-sessions")
async def list_project_test_sessions(
    project_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    UnityRunnerService(db).reconcile_project_tasks(project_id)
    query = db.query(TestSession).filter(TestSession.project_id == project_id)
    total = query.count()
    sessions = query.order_by(desc(TestSession.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "items": [_session_response(session) for session in sessions]}


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: Request,
    project_data: ProjectCreate,
    current_user: User = Depends(require_permission(Permission.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    project = Project(
        name=project_data.name,
        description=project_data.description,
        project_type=project_data.project_type,
        status=project_data.status,
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    await log_audit(
        db=db,
        action="project_create",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="project",
        resource_id=str(project.id),
        details={"name": project_data.name},
    )

    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    request: Request,
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(require_permission(Permission.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)

    await log_audit(
        db=db,
        action="project_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="project",
        resource_id=str(project_id),
        details=update_data,
    )

    return project


@router.delete("/{project_id}")
async def delete_project(
    request: Request,
    project_id: int,
    current_user: User = Depends(require_permission(Permission.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    project_name = project.name
    db.delete(project)
    db.commit()

    await log_audit(
        db=db,
        action="project_delete",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="project",
        resource_id=str(project_id),
        details={"name": project_name},
    )

    return {"message": "项目已删除"}
