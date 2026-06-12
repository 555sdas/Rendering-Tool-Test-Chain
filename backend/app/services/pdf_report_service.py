"""使用 reportlab 生成详细 PDF 报告（不依赖 xhtml2pdf / cairo）。"""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _register_cjk_font() -> str:
    candidates = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            font_name = "ReportCJK"
            pdfmetrics.registerFont(TTFont(font_name, path, subfontIndex=0))
            return font_name
        except Exception:
            continue
    return "Helvetica"


def _p(text: Any) -> str:
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _line_fits(text: str, font_name: str, font_size: float, max_width_pt: float) -> bool:
    return pdfmetrics.stringWidth(text, font_name, font_size) <= max_width_pt


def _wrap_segment(text: str, font_name: str, font_size: float, max_width_pt: float) -> list[str]:
    if _line_fits(text, font_name, font_size, max_width_pt):
        return [text]
    rows: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if _line_fits(candidate, font_name, font_size, max_width_pt):
            current = candidate
        else:
            if current:
                rows.append(current)
            current = ch
    if current:
        rows.append(current)
    return rows or [text]


def _wrap_log_line(
    line: str,
    *,
    font_name: str,
    font_size: float,
    max_width_pt: float,
) -> list[str]:
    """按 PDF 实际可排版宽度折行，优先在「 | 」分隔符处断开。"""
    text = line.rstrip()
    if not text:
        return [""]
    if _line_fits(text, font_name, font_size, max_width_pt):
        return [text]

    if " | " in text:
        parts = text.split(" | ")
        rows: list[str] = []
        current = parts[0]
        for part in parts[1:]:
            candidate = f"{current} | {part}"
            if _line_fits(candidate, font_name, font_size, max_width_pt):
                current = candidate
            else:
                if current:
                    rows.extend(_wrap_segment(current, font_name, font_size, max_width_pt))
                if _line_fits(part, font_name, font_size, max_width_pt):
                    current = part
                else:
                    rows.extend(_wrap_segment(part, font_name, font_size, max_width_pt))
                    current = ""
        if current:
            rows.extend(_wrap_segment(current, font_name, font_size, max_width_pt))
        return rows or _wrap_segment(text, font_name, font_size, max_width_pt)

    return _wrap_segment(text, font_name, font_size, max_width_pt)


def _append_wrapped_logs(
    story: list[Any],
    lines: list[str],
    style: ParagraphStyle,
    *,
    max_width_pt: float,
) -> None:
    if not lines:
        story.append(Paragraph(_p("无日志"), style))
        return

    font_name = style.fontName
    font_size = style.fontSize
    for line in lines:
        for chunk in _wrap_log_line(
            line,
            font_name=font_name,
            font_size=font_size,
            max_width_pt=max_width_pt,
        ):
            story.append(Paragraph(_p(chunk), style))


def build_detailed_pdf_from_context(context: dict[str, Any]) -> bytes:
    font_name = _register_cjk_font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=18,
        textColor=colors.HexColor("#0f3a5f"),
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=12,
        textColor=colors.HexColor("#0f3a5f"),
        spaceBefore=8,
        spaceAfter=4,
    )
    log_line_style = ParagraphStyle(
        "LogLine",
        parent=styles["Code"],
        fontName=font_name,
        fontSize=6,
        leading=8,
        textColor=colors.HexColor("#1e293b"),
        wordWrap="CJK",
        splitLongWords=1,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=7,
        leading=9,
        wordWrap="CJK",
        splitLongWords=1,
    )

    full_report = context.get("full_report") or {}
    fps = full_report.get("fps_analysis") or {}
    frame = full_report.get("frame_time_analysis") or {}
    memory = full_report.get("memory_analysis") or {}
    stability = full_report.get("stability_summary") or {}
    resource = full_report.get("resource_summary") or {}
    quality = full_report.get("render_quality_assessment") or {}
    violations = full_report.get("threshold_violations") or []
    session = context.get("session")

    story: list[Any] = [
        Paragraph(_p(context.get("title")), title_style),
        Paragraph(_p(f"生成时间：{context.get('generated_at')}"), ParagraphStyle("Meta", fontName=font_name, fontSize=9, textColor=colors.grey)),
        Spacer(1, 8),
    ]

    def add_table(title: str, rows: list[tuple[str, Any]]) -> None:
        story.append(Paragraph(_p(title), section_style))
        data = [["项目", "值"], *[[_p(k), _p(v)] for k, v in rows]]
        table = Table(data, colWidths=[55 * mm, 115 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f3a5f")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 6))

    add_table(
        "一、测试对象",
        [
            ("会话", getattr(session, "name", "-")),
            ("状态", context.get("session_status")),
            ("设备", getattr(session, "device_model", "-")),
            ("XR 运行时", getattr(session, "xr_runtime", "-")),
            ("样本数", context.get("sample_stats", {}).get("count")),
            ("运行时长(秒)", getattr(session, "duration_seconds", "-")),
        ],
    )
    add_table(
        "二、核心性能",
        [
            ("平均 FPS", fps.get("mean")),
            ("最低 FPS", fps.get("min")),
            ("P95 帧时间(ms)", frame.get("p95_ms")),
            ("P99 帧时间(ms)", frame.get("p99_ms")),
            ("长帧次数", stability.get("long_frame_count")),
            ("风险等级", stability.get("risk_level")),
            ("峰值内存(MB)", memory.get("max_mb")),
        ],
    )
    add_table(
        "三、资源复杂度",
        [
            ("平均 Draw Call", resource.get("avg_draw_calls")),
            ("平均 SetPass", resource.get("avg_set_pass_calls")),
            ("峰值纹理内存(MB)", resource.get("peak_texture_memory_mb")),
            ("峰值渲染纹理内存(MB)", resource.get("peak_render_texture_memory_mb")),
        ],
    )
    add_table(
        "四、渲染质量",
        [
            ("总体质量分", quality.get("overall_score")),
            ("等级", quality.get("grade")),
            ("数据完整度", quality.get("data_completeness")),
            ("置信等级", quality.get("confidence_grade")),
        ],
    )

    story.append(Paragraph(_p("五、质量大类评分明细"), section_style))
    cat_rows = [["维度", "权重", "得分", "状态"]]
    for cat in quality.get("categories") or []:
        score = "未测试" if cat.get("tested") is False or cat.get("score") is None else cat.get("score")
        cat_rows.append([_p(cat.get("name")), _p(f"{cat.get('weight')}%"), _p(score), _p(cat.get("status"))])
    cat_table = Table(cat_rows, colWidths=[40 * mm, 25 * mm, 25 * mm, 80 * mm])
    cat_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
            ]
        )
    )
    story.append(cat_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph(_p("六、质量子项明细"), section_style))
    metric_rows = [["子项", "状态", "数值", "说明"]]
    for row in context.get("quality_metric_rows") or []:
        metric_rows.append([_p(row.get("label")), _p(row.get("status_label")), _p(row.get("values")), _p(row.get("reason_label") or "-")])
    metric_table = Table(metric_rows, colWidths=[45 * mm, 25 * mm, 30 * mm, 70 * mm])
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
            ]
        )
    )
    story.append(metric_table)
    story.append(Spacer(1, 6))

    if violations:
        story.append(Paragraph(_p("七、阈值违规"), section_style))
        v_rows = [["规则", "指标", "阈值", "实际值"]]
        for item in violations[:30]:
            v_rows.append(
                [
                    _p(item.get("rule_name")),
                    _p(item.get("metric_name")),
                    _p(f"{item.get('operator')} {item.get('threshold_value')}"),
                    _p(item.get("actual_value")),
                ]
            )
        v_table = Table(v_rows, colWidths=[40 * mm, 35 * mm, 35 * mm, 60 * mm])
        v_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
                ]
            )
        )
        story.append(v_table)
        story.append(Spacer(1, 6))

    story.append(Paragraph(_p("八、运行日志"), section_style))
    runtime_logs = context.get("runtime_logs") or []
    _append_wrapped_logs(story, runtime_logs[:500], log_line_style, max_width_pt=doc.width)
    story.append(Spacer(1, 6))

    story.append(Paragraph(_p("九、审计日志"), section_style))
    audit_header = [
        Paragraph(_p("时间"), table_cell_style),
        Paragraph(_p("操作"), table_cell_style),
        Paragraph(_p("用户"), table_cell_style),
        Paragraph(_p("详情"), table_cell_style),
    ]
    audit_rows: list[list[Any]] = [audit_header]
    for item in context.get("audit_logs") or []:
        audit_rows.append(
            [
                Paragraph(_p(item.get("created_at")), table_cell_style),
                Paragraph(_p(item.get("action")), table_cell_style),
                Paragraph(_p(item.get("username")), table_cell_style),
                Paragraph(_p(item.get("details")), table_cell_style),
            ]
        )
    audit_table = Table(audit_rows, colWidths=[38 * mm, 28 * mm, 22 * mm, 82 * mm])
    audit_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
            ]
        )
    )
    story.append(audit_table)

    doc.build(story)
    return buffer.getvalue()
