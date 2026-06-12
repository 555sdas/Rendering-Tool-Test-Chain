"""构建详细测试报告上下文并渲染 HTML。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.performance_sample import PerformanceSample
from app.models.test_session import TestSession
from app.services.performance_analysis_service import PerformanceAnalysisService
from app.services.test_metric_catalog import QUALITY_METRIC_IDS
from app.services.test_scope_service import TestScopeService
from app.services.unity_runner_service import UnityRunnerService

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"

METRIC_STATUS_LABELS = {
    "skipped": "未纳入本次测试",
    "available": "数据可用",
    "unavailable": "当前环境不支持",
    "missing": "采集缺失",
    "failed": "采集失败",
}

SCORING_SOURCE_LABELS = {
    "session_snapshot": "会话创建时快照",
    "builtin_default": "系统内置默认（旧版测试）",
    "builtin_default_fallback": "快照无效，已回退默认",
}


class DetailedReportBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.analysis_service = PerformanceAnalysisService(db)

    def build_context(
        self,
        test_session_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        session = self.db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not session:
            raise ValueError("测试会话不存在")

        full_report = self.analysis_service.get_full_report(test_session_id)
        sample_stats = self._sample_stats(test_session_id)
        runtime_logs = self._collect_runtime_logs(session)
        audit_logs = self._collect_audit_logs(test_session_id)
        quality_rows = self._build_quality_metric_rows(full_report)
        config_pretty = json.dumps(session.config or {}, ensure_ascii=False, indent=2)

        device_info_pretty = None
        if sample_stats.get("device_info"):
            device_info_pretty = json.dumps(sample_stats["device_info"], ensure_ascii=False, indent=2)

        return {
            "title": title or f"{session.name} 详细测试报告",
            "description": description or "XR 渲染性能与视觉质量预测试详细报告",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session": session,
            "session_status": getattr(session.status, "value", session.status),
            "full_report": full_report,
            "sample_stats": sample_stats,
            "device_info_pretty": device_info_pretty,
            "runtime_logs": runtime_logs,
            "audit_logs": audit_logs,
            "quality_metric_rows": quality_rows,
            "config_pretty": config_pretty,
            "metric_status_labels": METRIC_STATUS_LABELS,
            "scoring_source_labels": SCORING_SOURCE_LABELS,
        }

    def render_html(self, context: dict[str, Any]) -> str:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
        )
        template = env.get_template("detailed_session_report.html.j2")
        return template.render(**context)

    def _sample_stats(self, test_session_id: int) -> dict[str, Any]:
        count = (
            self.db.query(func.count(PerformanceSample.id))
            .filter(PerformanceSample.test_session_id == test_session_id)
            .scalar()
            or 0
        )
        first = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .first()
        )
        last = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(desc(PerformanceSample.timestamp))
            .first()
        )
        device_info = None
        if first and isinstance(first.extra_metrics, dict):
            device_info = first.extra_metrics.get("device_info")
        return {
            "count": count,
            "first_timestamp": first.timestamp.isoformat() if first and first.timestamp else None,
            "last_timestamp": last.timestamp.isoformat() if last and last.timestamp else None,
            "device_info": device_info,
        }

    def _collect_runtime_logs(self, session: TestSession) -> list[str]:
        config = session.config or {}
        task_id = config.get("test_task_id")
        if not task_id:
            return ["未关联 Unity 测试任务，无 Runner/Unity 日志。"]

        try:
            payload = UnityRunnerService(self.db).get_task_logs(int(task_id), tail_lines=800)
            return payload.get("lines") or []
        except Exception as exc:
            return [f"读取运行日志失败：{exc}"]

    def _collect_audit_logs(self, test_session_id: int) -> list[dict[str, Any]]:
        rows = (
            self.db.query(AuditLog)
            .filter(AuditLog.resource_id == str(test_session_id))
            .order_by(AuditLog.created_at)
            .limit(200)
            .all()
        )
        return [
            {
                "created_at": row.created_at.isoformat() if row.created_at else "",
                "action": row.action,
                "username": row.username or "-",
                "resource_type": row.resource_type,
                "details": json.dumps(row.details or {}, ensure_ascii=False),
            }
            for row in rows
        ]

    def _build_quality_metric_rows(self, full_report: dict[str, Any]) -> list[dict[str, Any]]:
        quality = full_report.get("render_quality_assessment") or {}
        metric_status = quality.get("metric_status") or {}
        scope = full_report.get("test_scope") or {}
        catalog = TestScopeService.get_catalog()
        labels = {entry["id"]: entry.get("label", entry["id"]) for entry in catalog.get("quality_metrics", [])}

        rows: list[dict[str, Any]] = []
        for metric_id in QUALITY_METRIC_IDS:
            status_entry = metric_status.get(metric_id, {})
            status = status_entry.get("status", "skipped" if not TestScopeService.is_metric_enabled(scope, metric_id) else "missing")
            value_keys = status_entry.get("value_keys") or []
            category = metric_id.split(".")[0]
            category_metrics: dict[str, Any] = {}
            for cat in quality.get("categories") or []:
                parent = {
                    "lighting": "lighting",
                    "materials": "material",
                    "post_processing": "post_processing",
                    "physics": "physics",
                }.get(category)
                if cat.get("key") == parent:
                    category_metrics = cat.get("metrics") or {}
                    break
            values = [category_metrics.get(key) for key in value_keys if category_metrics.get(key) is not None]
            rows.append(
                {
                    "id": metric_id,
                    "label": labels.get(metric_id, metric_id),
                    "category": category,
                    "status": status,
                    "status_label": METRIC_STATUS_LABELS.get(status, status),
                    "reason_label": status_entry.get("reason_label"),
                    "values": ", ".join(str(v) for v in values) if values else "-",
                    "valid_sample_count": status_entry.get("valid_sample_count"),
                }
            )
        return rows
