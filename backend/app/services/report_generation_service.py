import html
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.test_report import ReportFormat, TestReport
from app.models.test_session import TestSession
from app.services.export_service import ExportService
from app.services.performance_analysis_service import PerformanceAnalysisService

settings = get_settings()


class ReportGenerationService:
    """生成面向验收和演示的轻量 HTML 测试报告。"""

    def __init__(self, db: Session):
        self.db = db
        self.analysis_service = PerformanceAnalysisService(db)
        self.export_service = ExportService(db)

    def generate_session_html_report(
        self,
        test_session_id: int,
        creator_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> TestReport:
        session = self.db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not session:
            raise ValueError("测试会话不存在")

        full_report = self.analysis_service.get_full_report(test_session_id)
        title = title or f"{session.name} 测试报告"
        report = self.export_service.create_report_record(
            title=title,
            creator_id=creator_id,
            project_id=session.project_id,
            test_session_ids=[test_session_id],
            format=ReportFormat.HTML,
            description=description or "系统自动生成的 XR 渲染性能预测试报告。",
        )

        output_dir = os.path.join(settings.UPLOAD_DIR, "reports")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"session_{test_session_id}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
        )

        html_text = self._build_html(title, session, full_report)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_text)

        summary = {
            "session_id": test_session_id,
            "risk_level": full_report.get("stability_summary", {}).get("risk_level"),
            "avg_fps": full_report.get("fps_analysis", {}).get("mean"),
            "p95_frame_time_ms": full_report.get("frame_time_analysis", {}).get("p95_ms"),
            "render_quality_score": full_report.get("render_quality_assessment", {}).get("overall_score"),
            "threshold_violation_count": len(full_report.get("threshold_violations", [])),
            "generated_for": "XR渲染性能与视觉质量预测试V1验收样例",
        }

        return self.export_service.update_report_file(
            report_id=report.id,
            file_path=output_path,
            file_size=os.path.getsize(output_path),
            summary=summary,
        )

    def _build_html(self, title: str, session: TestSession, report: dict) -> str:
        fps = report.get("fps_analysis", {})
        frame = report.get("frame_time_analysis", {})
        memory = report.get("memory_analysis", {})
        stability = report.get("stability_summary", {})
        resource = report.get("resource_summary", {})
        quality = report.get("render_quality_assessment", {})
        quality_categories = quality.get("categories", [])
        violations = report.get("threshold_violations", [])

        def row(name: str, value, unit: str = "") -> str:
            if value is None:
                value = "-"
            elif isinstance(value, float):
                value = f"{value:.2f}"
            return f"<tr><th>{html.escape(name)}</th><td>{html.escape(str(value))}{html.escape(unit)}</td></tr>"

        def quality_score_text(category: dict) -> str:
            score = category.get("score")
            if category.get("tested") is False or score is None:
                return "未测试"
            if isinstance(score, float):
                return f"{score:.2f}"
            return str(score)

        def quality_deductions_text(category: dict) -> str:
            if category.get("tested") is False:
                return "本次未勾选，不参与评分"
            deductions = category.get("deductions", [])
            return "; ".join(d.get("reason", "") for d in deductions) or "无明显扣分项"

        violation_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(v.get('rule_name', '-')))}</td>"
            f"<td>{html.escape(str(v.get('metric_name', '-')))}</td>"
            f"<td>{html.escape(str(v.get('operator', '-')))} {html.escape(str(v.get('threshold_value', '-')))}</td>"
            f"<td>{html.escape(str(v.get('actual_value', '-')))}</td>"
            f"<td>{html.escape(str(v.get('severity', '-')))}</td>"
            "</tr>"
            for v in violations
        ) or "<tr><td colspan='5'>未发现阈值违规。</td></tr>"

        quality_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(c.get('name', '-')))}</td>"
            f"<td>{html.escape(quality_score_text(c))}</td>"
            f"<td>{html.escape(str(c.get('status', '-')))}</td>"
            f"<td>{html.escape(quality_deductions_text(c))}</td>"
            f"<td>{html.escape('; '.join(c.get('recommendations', [])[:2]))}</td>"
            "</tr>"
            for c in quality_categories
        ) or "<tr><td colspan='5'>未生成渲染质量评分。</td></tr>"

        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 32px; color: #172033; }}
    h1, h2 {{ color: #0f3a5f; }}
    .meta {{ color: #5b6578; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d8dee9; padding: 8px 10px; text-align: left; }}
    th {{ background: #f4f7fb; width: 260px; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; background: #e8f3ff; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="meta">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 报告类型：XR 渲染性能与视觉质量预测试</p>

  <h2>一、测试对象</h2>
  <table>
    {row("测试会话", session.name)}
    {row("设备/平台", session.device_model)}
    {row("XR运行时", session.xr_runtime)}
    {row("应用版本", session.app_version)}
    {row("状态", getattr(session.status, "value", session.status))}
    {row("运行时长", session.duration_seconds, " 秒")}
  </table>

  <h2>二、核心性能指标</h2>
  <table>
    {row("平均 FPS", fps.get("mean"), " fps")}
    {row("最低 FPS", fps.get("min"), " fps")}
    {row("P95 帧时间", frame.get("p95_ms"), " ms")}
    {row("P99 帧时间", frame.get("p99_ms"), " ms")}
    {row("长帧次数", stability.get("long_frame_count"))}
    {row("掉帧率", (stability.get("dropped_frame_rate") or 0) * 100 if stability else None, "%")}
    {row("风险等级", stability.get("risk_level"))}
  </table>

  <h2>三、资源复杂度摘要</h2>
  <table>
    {row("平均 Draw Call", resource.get("avg_draw_calls"))}
    {row("平均 SetPass Call", resource.get("avg_set_pass_calls"))}
    {row("平均三角面数", resource.get("avg_triangle_count"))}
    {row("峰值纹理内存", resource.get("peak_texture_memory_mb"), " MB")}
    {row("峰值网格内存", resource.get("peak_mesh_memory_mb"), " MB")}
    {row("峰值渲染纹理内存", resource.get("peak_render_texture_memory_mb"), " MB")}
    {row("峰值内存", memory.get("max_mb"), " MB")}
  </table>

  <h2>四、渲染质量预测试评分</h2>
  <table>
    {row("总体质量分", quality.get("overall_score"))}
    {row("等级", quality.get("grade"))}
    {row("评估模式", (quality.get("evaluation_mode") or {}).get("description"))}
  </table>
  <table>
    <tr><th>维度</th><th>得分</th><th>状态</th><th>扣分依据</th><th>建议</th></tr>
    {quality_rows}
  </table>

  <h2>五、阈值与风险</h2>
  <table>
    <tr><th>规则</th><th>指标</th><th>阈值</th><th>实际值</th><th>级别</th></tr>
    {violation_rows}
  </table>

  <h2>六、结论与建议</h2>
  <p><span class="badge">{html.escape(str(stability.get("risk_level", "未评级")))}</span></p>
  <p>建议结合 Unity Profiler、RenderDoc 或设备厂商工具复核 GPU 瓶颈；对高 Draw Call、高纹理内存和长帧区间优先进行批处理、LOD、纹理压缩和渲染特性开关对比。</p>
  <p>本报告用于 V1 阶段预测试、辅助诊断和验收演示，不作为强制认证结论。</p>
</body>
</html>
"""
