from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.test_session import TestSession
from app.core.permissions import Permission, require_permission, get_current_user
from app.services.export_service import ExportService
from app.services.audit_service import log_audit

router = APIRouter(prefix="/exports", tags=["数据导出"])


class ExportRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    format: str = Field(..., pattern="^(csv|excel|json)$")


@router.post("/samples")
async def export_samples(
    request: Request,
    export_data: ExportRequest,
    current_user: User = Depends(require_permission(Permission.DATA_EXPORT)),
    db: Session = Depends(get_db),
):
    session = db.query(TestSession).filter(TestSession.id == export_data.session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试会话不存在",
        )

    service = ExportService(db)

    try:
        if export_data.format == "csv":
            file_path = service.export_samples_to_csv(export_data.session_id)
        elif export_data.format == "excel":
            file_path = service.export_samples_to_excel(export_data.session_id)
        elif export_data.format == "json":
            file_path = service.export_samples_to_json(export_data.session_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的导出格式",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await log_audit(
        db=db,
        action="report_export",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_session",
        resource_id=str(export_data.session_id),
        details={"format": export_data.format, "file_path": file_path},
    )

    return {
        "message": "导出成功",
        "file_path": file_path,
        "format": export_data.format,
    }
