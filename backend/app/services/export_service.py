import os
import json
import tempfile
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
import pandas as pd
from app.models.performance_sample import PerformanceSample
from app.models.test_session import TestSession
from app.models.test_report import TestReport, ReportFormat
from app.config import get_settings

settings = get_settings()


class ExportService:
    def __init__(self, db: Session):
        self.db = db

    def export_samples_to_csv(
        self,
        test_session_id: int,
        output_path: Optional[str] = None,
    ) -> str:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .all()
        )

        if not samples:
            raise ValueError("没有可导出的数据")

        data = []
        for s in samples:
            data.append({
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "frame_time_ms": s.frame_time_ms,
                "fps": s.fps,
                "cpu_usage_percent": s.cpu_usage_percent,
                "gpu_usage_percent": s.gpu_usage_percent,
                "memory_mb": s.memory_mb,
                "battery_level": s.battery_level,
                "battery_temperature": s.battery_temperature,
                "draw_calls": s.draw_calls,
                "triangle_count": s.triangle_count,
                "vertex_count": s.vertex_count,
                "set_pass_calls": s.set_pass_calls,
                "texture_memory_mb": s.texture_memory_mb,
                "mesh_memory_mb": s.mesh_memory_mb,
                "render_texture_memory_mb": s.render_texture_memory_mb,
                "gc_collect_count": s.gc_collect_count,
                "gc_allocated_mb": s.gc_allocated_mb,
                "screen_resolution": s.screen_resolution,
                "tracking_state": s.tracking_state,
                "prediction_error_ms": s.prediction_error_ms,
                "pose_latency_ms": s.pose_latency_ms,
            })

        df = pd.DataFrame(data)

        if not output_path:
            output_path = os.path.join(
                settings.UPLOAD_DIR,
                f"session_{test_session_id}_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def export_samples_to_excel(
        self,
        test_session_id: int,
        output_path: Optional[str] = None,
    ) -> str:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .all()
        )

        if not samples:
            raise ValueError("没有可导出的数据")

        data = []
        for s in samples:
            data.append({
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "frame_time_ms": s.frame_time_ms,
                "fps": s.fps,
                "cpu_usage_percent": s.cpu_usage_percent,
                "gpu_usage_percent": s.gpu_usage_percent,
                "memory_mb": s.memory_mb,
                "battery_level": s.battery_level,
                "battery_temperature": s.battery_temperature,
                "draw_calls": s.draw_calls,
                "triangle_count": s.triangle_count,
                "vertex_count": s.vertex_count,
                "set_pass_calls": s.set_pass_calls,
                "texture_memory_mb": s.texture_memory_mb,
                "mesh_memory_mb": s.mesh_memory_mb,
                "render_texture_memory_mb": s.render_texture_memory_mb,
                "gc_collect_count": s.gc_collect_count,
                "gc_allocated_mb": s.gc_allocated_mb,
                "screen_resolution": s.screen_resolution,
                "tracking_state": s.tracking_state,
                "prediction_error_ms": s.prediction_error_ms,
                "pose_latency_ms": s.pose_latency_ms,
            })

        df = pd.DataFrame(data)

        if not output_path:
            output_path = os.path.join(
                settings.UPLOAD_DIR,
                f"session_{test_session_id}_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Samples", index=False)

            summary_data = {
                "metric": ["FPS", "Frame Time (ms)", "CPU (%)", "GPU (%)", "Memory (MB)", "Battery Temp (C)"],
                "mean": [
                    df["fps"].mean() if "fps" in df.columns else None,
                    df["frame_time_ms"].mean() if "frame_time_ms" in df.columns else None,
                    df["cpu_usage_percent"].mean() if "cpu_usage_percent" in df.columns else None,
                    df["gpu_usage_percent"].mean() if "gpu_usage_percent" in df.columns else None,
                    df["memory_mb"].mean() if "memory_mb" in df.columns else None,
                    df["battery_temperature"].mean() if "battery_temperature" in df.columns else None,
                ],
                "min": [
                    df["fps"].min() if "fps" in df.columns else None,
                    df["frame_time_ms"].min() if "frame_time_ms" in df.columns else None,
                    df["cpu_usage_percent"].min() if "cpu_usage_percent" in df.columns else None,
                    df["gpu_usage_percent"].min() if "gpu_usage_percent" in df.columns else None,
                    df["memory_mb"].min() if "memory_mb" in df.columns else None,
                    df["battery_temperature"].min() if "battery_temperature" in df.columns else None,
                ],
                "max": [
                    df["fps"].max() if "fps" in df.columns else None,
                    df["frame_time_ms"].max() if "frame_time_ms" in df.columns else None,
                    df["cpu_usage_percent"].max() if "cpu_usage_percent" in df.columns else None,
                    df["gpu_usage_percent"].max() if "gpu_usage_percent" in df.columns else None,
                    df["memory_mb"].max() if "memory_mb" in df.columns else None,
                    df["battery_temperature"].max() if "battery_temperature" in df.columns else None,
                ],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

        return output_path

    def export_samples_to_json(
        self,
        test_session_id: int,
        output_path: Optional[str] = None,
    ) -> str:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .all()
        )

        if not samples:
            raise ValueError("没有可导出的数据")

        data = []
        for s in samples:
            sample_dict = {
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "frame_time_ms": s.frame_time_ms,
                "fps": s.fps,
                "cpu_usage_percent": s.cpu_usage_percent,
                "gpu_usage_percent": s.gpu_usage_percent,
                "memory_mb": s.memory_mb,
                "battery_level": s.battery_level,
                "battery_temperature": s.battery_temperature,
                "draw_calls": s.draw_calls,
                "triangle_count": s.triangle_count,
                "vertex_count": s.vertex_count,
                "set_pass_calls": s.set_pass_calls,
                "texture_memory_mb": s.texture_memory_mb,
                "mesh_memory_mb": s.mesh_memory_mb,
                "render_texture_memory_mb": s.render_texture_memory_mb,
                "gc_collect_count": s.gc_collect_count,
                "gc_allocated_mb": s.gc_allocated_mb,
                "screen_resolution": s.screen_resolution,
                "tracking_state": s.tracking_state,
                "prediction_error_ms": s.prediction_error_ms,
                "pose_latency_ms": s.pose_latency_ms,
                "extra_metrics": s.extra_metrics,
            }
            data.append({k: v for k, v in sample_dict.items() if v is not None})

        if not output_path:
            output_path = os.path.join(
                settings.UPLOAD_DIR,
                f"session_{test_session_id}_samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return output_path

    def create_report_record(
        self,
        title: str,
        creator_id: int,
        project_id: Optional[int] = None,
        test_session_ids: Optional[list] = None,
        format: ReportFormat = ReportFormat.PDF,
        description: Optional[str] = None,
    ) -> TestReport:
        report = TestReport(
            title=title,
            creator_id=creator_id,
            project_id=project_id,
            test_session_ids=test_session_ids,
            format=format,
            description=description,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def update_report_file(
        self,
        report_id: int,
        file_path: str,
        file_size: int,
        summary: Optional[dict] = None,
    ) -> TestReport:
        report = self.db.query(TestReport).filter(TestReport.id == report_id).first()
        if not report:
            raise ValueError("报告不存在")

        report.file_path = file_path
        report.file_size = file_size
        report.summary = summary
        report.generated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(report)
        return report
