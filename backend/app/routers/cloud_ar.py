from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.permissions import Permission, get_current_user, require_permission
from app.database import get_db
from app.models.cloud_ar_session import CloudARSession, CloudARSessionStatus
from app.models.user import User
from app.services.audit_service import log_audit

router = APIRouter(prefix="/cloud-ar", tags=["云AR协同测试"])


class CloudARSessionCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    project_id: Optional[int] = None
    scene_id: Optional[int] = None
    server_endpoint: Optional[str] = None
    stream_quality: Optional[str] = None
    latency_ms: Optional[float] = None
    bandwidth_mbps: Optional[float] = None
    packet_loss_percent: Optional[float] = None
    encoding_preset: Optional[str] = None
    resolution: Optional[str] = None
    frame_rate: Optional[int] = None
    bit_rate_kbps: Optional[int] = None
    config: Optional[dict] = None
    participants: Optional[list] = None


class CloudARSessionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[CloudARSessionStatus] = None
    stream_quality: Optional[str] = None
    latency_ms: Optional[float] = None
    bandwidth_mbps: Optional[float] = None
    packet_loss_percent: Optional[float] = None
    config: Optional[dict] = None
    participants: Optional[list] = None
    error_message: Optional[str] = None


@router.get("/sessions")
async def list_cloud_ar_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    project_id: Optional[int] = None,
    session_status: Optional[CloudARSessionStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CloudARSession)
    if project_id:
        query = query.filter(CloudARSession.project_id == project_id)
    if session_status:
        query = query.filter(CloudARSession.status == session_status.value)
    total = query.count()
    items = query.order_by(desc(CloudARSession.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/sessions/{session_id}")
async def get_cloud_ar_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cloud_session = db.query(CloudARSession).filter(CloudARSession.session_id == session_id).first()
    if not cloud_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="云AR会话不存在")
    return cloud_session


@router.post("/sessions")
async def create_cloud_ar_session(
    request: Request,
    data: CloudARSessionCreate,
    current_user: User = Depends(require_permission(Permission.CLOUD_AR_MANAGE)),
    db: Session = Depends(get_db),
):
    exists = db.query(CloudARSession).filter(CloudARSession.session_id == data.session_id).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="云AR会话ID已存在")

    cloud_session = CloudARSession(
        session_id=data.session_id,
        name=data.name,
        description=data.description,
        user_id=current_user.id,
        project_id=data.project_id,
        scene_id=data.scene_id,
        server_endpoint=data.server_endpoint,
        stream_quality=data.stream_quality,
        latency_ms=data.latency_ms,
        bandwidth_mbps=data.bandwidth_mbps,
        packet_loss_percent=data.packet_loss_percent,
        encoding_preset=data.encoding_preset,
        resolution=data.resolution,
        frame_rate=data.frame_rate,
        bit_rate_kbps=data.bit_rate_kbps,
        config=data.config,
        participants=data.participants,
    )
    db.add(cloud_session)
    db.commit()
    db.refresh(cloud_session)

    await log_audit(
        db=db,
        action="cloud_ar_session_create",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="cloud_ar_session",
        resource_id=cloud_session.session_id,
        details={"name": cloud_session.name, "participants": len(data.participants or [])},
    )
    return cloud_session


@router.put("/sessions/{session_id}")
async def update_cloud_ar_session(
    request: Request,
    session_id: str,
    data: CloudARSessionUpdate,
    current_user: User = Depends(require_permission(Permission.CLOUD_AR_MANAGE)),
    db: Session = Depends(get_db),
):
    cloud_session = db.query(CloudARSession).filter(CloudARSession.session_id == session_id).first()
    if not cloud_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="云AR会话不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value
        if update_data["status"] in {CloudARSessionStatus.ACTIVE.value, CloudARSessionStatus.STREAMING.value}:
            cloud_session.started_at = cloud_session.started_at or datetime.utcnow()
        if update_data["status"] in {CloudARSessionStatus.CLOSED.value, CloudARSessionStatus.ERROR.value}:
            cloud_session.ended_at = datetime.utcnow()
            if cloud_session.started_at:
                cloud_session.duration_seconds = (cloud_session.ended_at - cloud_session.started_at).total_seconds()

    for field, value in update_data.items():
        setattr(cloud_session, field, value)
    db.commit()
    db.refresh(cloud_session)

    await log_audit(
        db=db,
        action="cloud_ar_session_update",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="cloud_ar_session",
        resource_id=session_id,
        details=update_data,
    )
    return cloud_session


@router.delete("/sessions/{session_id}")
async def delete_cloud_ar_session(
    session_id: str,
    current_user: User = Depends(require_permission(Permission.CLOUD_AR_MANAGE)),
    db: Session = Depends(get_db),
):
    cloud_session = db.query(CloudARSession).filter(CloudARSession.session_id == session_id).first()
    if not cloud_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="云AR会话不存在")
    db.delete(cloud_session)
    db.commit()
    return {"message": "云AR会话已删除"}
