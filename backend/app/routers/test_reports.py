import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.test_report import TestReport, ReportFormat
from app.core.permissions import Permission, require_permission, get_current_user
from app.services.audit_service import log_audit
from app.services.export_service import ExportService
from app.services.report_generation_service import ReportGenerationService

router = APIRouter(prefix="/test-reports", tags=["测试报告"])


class TestReportCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    project_id: Optional[int] = None
    test_session_ids: Optional[list[int]] = None
    format: str = Field(default=ReportFormat.PDF.value)


class TestReportUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    project_id: Optional[int] = None
    test_session_ids: Optional[list[int]] = None
    format: Optional[str] = None


class GenerateSessionReportRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class TestReportResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    project_id: Optional[int]
    test_session_ids: Optional[list]
    creator_id: Optional[int]
    format: str
    file_path: Optional[str]
    file_size: Optional[int]
    summary: Optional[dict]
    generated_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


def _report_media_type(report_format: str | ReportFormat | None) -> str:
    value = getattr(report_format, "value", report_format)
    if value == ReportFormat.HTML.value:
        return "text/html; charset=utf-8"
    if value == ReportFormat.EXCEL.value:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if value == ReportFormat.WORD.value:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if value == ReportFormat.PDF.value:
        return "application/pdf"
    return "application/octet-stream"


@router.get("", response_model=list[TestReportResponse])
async def list_test_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(TestReport)
    if project_id:
        query = query.filter(TestReport.project_id == project_id)

    reports = query.order_by(desc(TestReport.created_at)).offset(skip).limit(limit).all()
    return reports


@router.get("/{report_id}", response_model=TestReportResponse)
async def get_test_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在",
        )
    return report


@router.post("", response_model=TestReportResponse)
async def create_test_report(
    request: Request,
    report_data: TestReportCreate,
    current_user: User = Depends(require_permission(Permission.REPORT_CREATE)),
    db: Session = Depends(get_db),
):
    service = ExportService(db)
    report = service.create_report_record(
        title=report_data.title,
        creator_id=current_user.id,
        project_id=report_data.project_id,
        test_session_ids=report_data.test_session_ids,
        format=ReportFormat(report_data.format),
        description=report_data.description,
    )

    await log_audit(
        db=db,
        action="report_generate",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_report",
        resource_id=str(report.id),
        details={"title": report_data.title},
    )

    return report


@router.get("/{report_id}/download")
async def download_test_report(
    report_id: int,
    current_user: User = Depends(require_permission(Permission.REPORT_VIEW)),
    db: Session = Depends(get_db),
):
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在",
        )

    if not report.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告尚未生成文件",
        )

    file_path = os.path.abspath(report.file_path)
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告文件不存在",
        )

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type=_report_media_type(report.format),
    )


@router.post("/generate-from-session/{session_id}", response_model=TestReportResponse)
async def generate_report_from_session(
    request: Request,
    session_id: int,
    report_data: GenerateSessionReportRequest | None = None,
    current_user: User = Depends(require_permission(Permission.REPORT_CREATE)),
    db: Session = Depends(get_db),
):
    service = ReportGenerationService(db)
    try:
        report = service.generate_session_html_report(
            test_session_id=session_id,
            creator_id=current_user.id,
            title=report_data.title if report_data else None,
            description=report_data.description if report_data else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await log_audit(
        db=db,
        action="report_generate",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request.client else None,
        resource_type="test_report",
        resource_id=str(report.id),
        details={"session_id": session_id, "file_path": report.file_path},
    )
    return report


@router.put("/{report_id}", response_model=TestReportResponse)
async def update_test_report(
    request: Request,
    report_id: int,
    report_data: TestReportUpdate,
    current_user: User = Depends(require_permission(Permission.REPORT_CREATE)),
    db: Session = Depends(get_db),
):
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在",
        )

    update_data = report_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)

    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)

    return report


@router.delete("/{report_id}")
async def delete_test_report(
    request: Request,
    report_id: int,
    current_user: User = Depends(require_permission(Permission.REPORT_CREATE)),
    db: Session = Depends(get_db),
):
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在",
        )

    db.delete(report)
    db.commit()

    return {"message": "测试报告已删除"}
