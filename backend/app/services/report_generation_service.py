import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.test_report import ReportFormat, TestReport
from app.models.test_session import TestSession
from app.services.detailed_report_builder import DetailedReportBuilder
from app.services.export_service import ExportService
from app.services.pdf_report_service import build_detailed_pdf_from_context

settings = get_settings()


class ReportGenerationService:
    """生成详细 HTML / PDF 测试报告。"""

    def __init__(self, db: Session):
        self.db = db
        self.builder = DetailedReportBuilder(db)
        self.export_service = ExportService(db)

    def generate_session_report(
        self,
        test_session_id: int,
        creator_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        report_format: str = ReportFormat.HTML.value,
    ) -> TestReport:
        session = self.db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not session:
            raise ValueError("测试会话不存在")

        normalized_format = (report_format or ReportFormat.HTML.value).lower()
        if normalized_format not in {ReportFormat.HTML.value, ReportFormat.PDF.value}:
            raise ValueError("仅支持 html 或 pdf 格式")

        context = self.builder.build_context(test_session_id, title=title, description=description)
        html_text = self.builder.render_html(context)
        report_title = context["title"]
        full_report = context["full_report"]
        quality = full_report.get("render_quality_assessment") or {}
        stability = full_report.get("stability_summary") or {}

        report = self.export_service.create_report_record(
            title=report_title,
            creator_id=creator_id,
            project_id=session.project_id,
            test_session_ids=[test_session_id],
            format=ReportFormat(normalized_format),
            description=description or "系统自动生成的 XR 渲染性能详细测试报告。",
        )

        output_dir = os.path.join(settings.UPLOAD_DIR, "reports")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = "pdf" if normalized_format == ReportFormat.PDF.value else "html"
        output_path = os.path.join(output_dir, f"session_{test_session_id}_report_{timestamp}.{extension}")

        if normalized_format == ReportFormat.HTML.value:
            with open(output_path, "w", encoding="utf-8") as file:
                file.write(html_text)
        else:
            pdf_bytes = build_detailed_pdf_from_context(context)
            with open(output_path, "wb") as file:
                file.write(pdf_bytes)

        summary = {
            "session_id": test_session_id,
            "risk_level": stability.get("risk_level"),
            "avg_fps": full_report.get("fps_analysis", {}).get("mean"),
            "p95_frame_time_ms": full_report.get("frame_time_analysis", {}).get("p95_ms"),
            "render_quality_score": quality.get("overall_score"),
            "threshold_violation_count": len(full_report.get("threshold_violations", [])),
            "sample_count": context["sample_stats"]["count"],
            "format": normalized_format,
            "generated_for": "XR渲染性能与视觉质量预测试详细报告",
        }

        return self.export_service.update_report_file(
            report_id=report.id,
            file_path=output_path,
            file_size=os.path.getsize(output_path),
            summary=summary,
        )

    def generate_session_html_report(
        self,
        test_session_id: int,
        creator_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TestReport:
        return self.generate_session_report(
            test_session_id,
            creator_id,
            title=title,
            description=description,
            report_format=ReportFormat.HTML.value,
        )
