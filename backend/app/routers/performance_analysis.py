from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.threshold_rule import ThresholdRule, ThresholdSeverity
from app.core.permissions import Permission, require_permission, get_current_user
from app.services.performance_analysis_service import PerformanceAnalysisService
from app.services.render_quality_service import RenderQualityService

router = APIRouter(prefix="/performance", tags=["性能分析"])


class ThresholdRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    metric_name: str = Field(..., min_length=1, max_length=100)
    operator: str = Field(..., pattern="^(>|>=|<|<=|==|!=)$")
    threshold_value: float
    severity: ThresholdSeverity = ThresholdSeverity.WARNING
    device_filter: Optional[str] = None
    scene_filter: Optional[str] = None
    project_id: Optional[int] = None
    auto_alert: bool = False
    alert_channels: Optional[list] = None


class ThresholdRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    metric_name: Optional[str] = Field(None, min_length=1, max_length=100)
    operator: Optional[str] = Field(None, pattern="^(>|>=|<|<=|==|!=)$")
    threshold_value: Optional[float] = None
    severity: Optional[ThresholdSeverity] = None
    device_filter: Optional[str] = None
    scene_filter: Optional[str] = None
    is_active: Optional[bool] = None
    auto_alert: Optional[bool] = None
    alert_channels: Optional[list] = None


@router.get("/analysis/{session_id}/fps")
async def get_fps_analysis(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.get_fps_analysis(session_id)


@router.get("/analysis/{session_id}/frame-time")
async def get_frame_time_analysis(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.get_frame_time_analysis(session_id)


@router.get("/analysis/{session_id}/memory")
async def get_memory_analysis(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.get_memory_analysis(session_id)


@router.get("/analysis/{session_id}/thermal")
async def get_thermal_analysis(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.get_thermal_analysis(session_id)


@router.get("/analysis/{session_id}/thresholds")
async def check_thresholds(
    session_id: int,
    project_id: Optional[int] = None,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.check_thresholds(session_id, project_id)


@router.get("/analysis/{session_id}/full-report")
async def get_full_report(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.get_full_report(session_id)


@router.get("/analysis/{session_id}/render-quality")
async def get_render_quality_assessment(
    session_id: int,
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = RenderQualityService(db)
    return service.evaluate_session(session_id)


@router.get("/trend")
async def get_trend_analysis(
    session_ids: list[int] = Query(...),
    metric: str = Query("fps"),
    current_user: User = Depends(require_permission(Permission.TEST_VIEW)),
    db: Session = Depends(get_db),
):
    service = PerformanceAnalysisService(db)
    return service.get_trend_analysis(session_ids, metric)


@router.get("/threshold-rules")
async def list_threshold_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    project_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_permission(Permission.THRESHOLD_MANAGE)),
    db: Session = Depends(get_db),
):
    query = db.query(ThresholdRule)
    if project_id is not None:
        query = query.filter(
            (ThresholdRule.project_id == project_id) | (ThresholdRule.project_id.is_(None))
        )
    if is_active is not None:
        query = query.filter(ThresholdRule.is_active == is_active)

    total = query.count()
    rules = query.offset(skip).limit(limit).all()
    return {"total": total, "items": rules}


@router.post("/threshold-rules")
async def create_threshold_rule(
    rule_data: ThresholdRuleCreate,
    current_user: User = Depends(require_permission(Permission.THRESHOLD_MANAGE)),
    db: Session = Depends(get_db),
):
    rule = ThresholdRule(
        name=rule_data.name,
        description=rule_data.description,
        metric_name=rule_data.metric_name,
        operator=rule_data.operator,
        threshold_value=rule_data.threshold_value,
        severity=rule_data.severity,
        device_filter=rule_data.device_filter,
        scene_filter=rule_data.scene_filter,
        project_id=rule_data.project_id,
        auto_alert=rule_data.auto_alert,
        alert_channels=rule_data.alert_channels,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/threshold-rules/{rule_id}")
async def get_threshold_rule(
    rule_id: int,
    current_user: User = Depends(require_permission(Permission.THRESHOLD_MANAGE)),
    db: Session = Depends(get_db),
):
    rule = db.query(ThresholdRule).filter(ThresholdRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="阈值规则不存在",
        )
    return rule


@router.put("/threshold-rules/{rule_id}")
async def update_threshold_rule(
    rule_id: int,
    rule_data: ThresholdRuleUpdate,
    current_user: User = Depends(require_permission(Permission.THRESHOLD_MANAGE)),
    db: Session = Depends(get_db),
):
    rule = db.query(ThresholdRule).filter(ThresholdRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="阈值规则不存在",
        )

    update_data = rule_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/threshold-rules/{rule_id}")
async def delete_threshold_rule(
    rule_id: int,
    current_user: User = Depends(require_permission(Permission.THRESHOLD_MANAGE)),
    db: Session = Depends(get_db),
):
    rule = db.query(ThresholdRule).filter(ThresholdRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="阈值规则不存在",
        )

    db.delete(rule)
    db.commit()
    return {"message": "阈值规则已删除"}
