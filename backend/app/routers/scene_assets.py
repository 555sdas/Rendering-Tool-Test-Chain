from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.scene_asset import SceneAsset, AssetType
from app.core.permissions import Permission, require_permission, get_current_user
from app.services.audit_service import log_audit

router = APIRouter(prefix="/scene-assets", tags=["场景资源管理"])


class SceneAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    asset_type: str = Field(..., min_length=1, max_length=20)
    file_path: str = Field(..., min_length=1, max_length=500)
    file_size: int = Field(default=0, ge=0)
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[list] = None
    asset_metadata: Optional[dict] = None
    complexity_score: Optional[float] = None
    polygon_count: Optional[int] = None
    texture_count: Optional[int] = None
    light_count: Optional[int] = None
    particle_count: Optional[int] = None
    is_public: bool = False
    project_id: Optional[int] = None


class SceneAssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    asset_type: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[list] = None
    asset_metadata: Optional[dict] = None
    complexity_score: Optional[float] = None
    polygon_count: Optional[int] = None
    texture_count: Optional[int] = None
    light_count: Optional[int] = None
    particle_count: Optional[int] = None
    is_public: Optional[bool] = None
    project_id: Optional[int] = None


class SceneAssetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    asset_type: str
    file_path: str
    file_size: int
    file_hash: Optional[str]
    mime_type: Optional[str]
    version: Optional[str]
    tags: Optional[list]
    asset_metadata: Optional[dict]
    complexity_score: Optional[float]
    polygon_count: Optional[int]
    texture_count: Optional[int]
    light_count: Optional[int]
    particle_count: Optional[int]
    is_public: bool
    project_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("", response_model=list[SceneAssetResponse])
async def list_scene_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    asset_type: Optional[str] = None,
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SceneAsset)
    if search:
        query = query.filter(SceneAsset.name.ilike(f"%{search}%"))
    if asset_type:
        query = query.filter(SceneAsset.asset_type == asset_type)
    if project_id:
        query = query.filter(SceneAsset.project_id == project_id)

    assets = query.order_by(desc(SceneAsset.created_at)).offset(skip).limit(limit).all()
    return assets


@router.get("/{asset_id}", response_model=SceneAssetResponse)
async def get_scene_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    asset = db.query(SceneAsset).filter(SceneAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="场景资源不存在",
        )
    return asset


@router.post("", response_model=SceneAssetResponse)
async def create_scene_asset(
    request: Request,
    asset_data: SceneAssetCreate,
    current_user: User = Depends(require_permission(Permission.SCENE_MANAGE)),
    db: Session = Depends(get_db),
):
    asset = SceneAsset(
        name=asset_data.name,
        description=asset_data.description,
        asset_type=asset_data.asset_type,
        file_path=asset_data.file_path,
        file_size=asset_data.file_size,
        file_hash=asset_data.file_hash,
        mime_type=asset_data.mime_type,
        version=asset_data.version,
        tags=asset_data.tags,
        asset_metadata=asset_data.asset_metadata,
        complexity_score=asset_data.complexity_score,
        polygon_count=asset_data.polygon_count,
        texture_count=asset_data.texture_count,
        light_count=asset_data.light_count,
        particle_count=asset_data.particle_count,
        is_public=asset_data.is_public,
        project_id=asset_data.project_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    await log_audit(
        db=db,
        action="scene_upload",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="scene_asset",
        resource_id=str(asset.id),
        details={"name": asset_data.name, "type": asset_data.asset_type},
    )

    return asset


@router.put("/{asset_id}", response_model=SceneAssetResponse)
async def update_scene_asset(
    request: Request,
    asset_id: int,
    asset_data: SceneAssetUpdate,
    current_user: User = Depends(require_permission(Permission.SCENE_MANAGE)),
    db: Session = Depends(get_db),
):
    asset = db.query(SceneAsset).filter(SceneAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="场景资源不存在",
        )

    update_data = asset_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)

    asset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)

    await log_audit(
        db=db,
        action="scene_upload",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="scene_asset",
        resource_id=str(asset_id),
        details=update_data,
    )

    return asset


@router.delete("/{asset_id}")
async def delete_scene_asset(
    request: Request,
    asset_id: int,
    current_user: User = Depends(require_permission(Permission.SCENE_MANAGE)),
    db: Session = Depends(get_db),
):
    asset = db.query(SceneAsset).filter(SceneAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="场景资源不存在",
        )

    asset_name = asset.name
    db.delete(asset)
    db.commit()

    await log_audit(
        db=db,
        action="scene_delete",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="scene_asset",
        resource_id=str(asset_id),
        details={"name": asset_name},
    )

    return {"message": "场景资源已删除"}
