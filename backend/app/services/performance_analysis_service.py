from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import numpy as np
from scipy import stats
from app.models.performance_sample import PerformanceSample
from app.models.test_session import TestSession
from app.models.threshold_rule import ThresholdRule
from app.services.render_quality_service import RenderQualityService


class PerformanceAnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def get_fps_analysis(self, test_session_id: int) -> dict:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .filter(PerformanceSample.fps.isnot(None))
            .all()
        )

        if not samples:
            return {}

        fps_values = np.array([s.fps for s in samples])

        return {
            "count": len(fps_values),
            "mean": float(np.mean(fps_values)),
            "median": float(np.median(fps_values)),
            "std": float(np.std(fps_values)),
            "min": float(np.min(fps_values)),
            "max": float(np.max(fps_values)),
            "p1": float(np.percentile(fps_values, 1)),
            "p5": float(np.percentile(fps_values, 5)),
            "p95": float(np.percentile(fps_values, 95)),
            "p99": float(np.percentile(fps_values, 99)),
            "below_30_count": int(np.sum(fps_values < 30)),
            "below_60_count": int(np.sum(fps_values < 60)),
            "jank_count": int(np.sum(np.diff(fps_values) < -10)),
        }

    def get_frame_time_analysis(self, test_session_id: int) -> dict:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .filter(PerformanceSample.frame_time_ms.isnot(None))
            .all()
        )

        if not samples:
            return {}

        frame_times = np.array([s.frame_time_ms for s in samples])

        return {
            "count": len(frame_times),
            "mean_ms": float(np.mean(frame_times)),
            "median_ms": float(np.median(frame_times)),
            "std_ms": float(np.std(frame_times)),
            "min_ms": float(np.min(frame_times)),
            "max_ms": float(np.max(frame_times)),
            "p90_ms": float(np.percentile(frame_times, 90)),
            "p95_ms": float(np.percentile(frame_times, 95)),
            "p99_ms": float(np.percentile(frame_times, 99)),
            "above_16_6ms_count": int(np.sum(frame_times > 16.67)),
            "above_33_3ms_count": int(np.sum(frame_times > 33.33)),
        }

    def get_memory_analysis(self, test_session_id: int) -> dict:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .filter(PerformanceSample.memory_mb.isnot(None))
            .all()
        )

        if not samples:
            return {}

        memory_values = np.array([s.memory_mb for s in samples])

        return {
            "count": len(memory_values),
            "mean_mb": float(np.mean(memory_values)),
            "median_mb": float(np.median(memory_values)),
            "min_mb": float(np.min(memory_values)),
            "max_mb": float(np.max(memory_values)),
            "std_mb": float(np.std(memory_values)),
            "growth_rate_mb_per_min": None,
        }

    def get_thermal_analysis(self, test_session_id: int) -> dict:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .filter(PerformanceSample.battery_temperature.isnot(None))
            .all()
        )

        if not samples:
            return {}

        temps = np.array([s.battery_temperature for s in samples])

        return {
            "count": len(temps),
            "mean_c": float(np.mean(temps)),
            "max_c": float(np.max(temps)),
            "min_c": float(np.min(temps)),
            "above_40_count": int(np.sum(temps > 40)),
            "above_45_count": int(np.sum(temps > 45)),
        }

    def check_thresholds(self, test_session_id: int, project_id: Optional[int] = None) -> list[dict]:
        session = self.db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not session:
            return []

        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .all()
        )

        if not samples:
            return []

        query = self.db.query(ThresholdRule).filter(ThresholdRule.is_active == True)
        if project_id:
            query = query.filter(
                (ThresholdRule.project_id == project_id) | (ThresholdRule.project_id.is_(None))
            )
        rules = query.all()

        violations = []
        metric_map = {
            "fps": [s.fps for s in samples if s.fps is not None],
            "frame_time_ms": [s.frame_time_ms for s in samples if s.frame_time_ms is not None],
            "cpu_usage_percent": [s.cpu_usage_percent for s in samples if s.cpu_usage_percent is not None],
            "gpu_usage_percent": [s.gpu_usage_percent for s in samples if s.gpu_usage_percent is not None],
            "memory_mb": [s.memory_mb for s in samples if s.memory_mb is not None],
            "battery_temperature": [s.battery_temperature for s in samples if s.battery_temperature is not None],
            "draw_calls": [s.draw_calls for s in samples if s.draw_calls is not None],
        }

        for rule in rules:
            values = metric_map.get(rule.metric_name, [])
            if not values:
                continue

            avg_value = sum(values) / len(values)
            violated = False

            if rule.operator == ">" and avg_value > rule.threshold_value:
                violated = True
            elif rule.operator == ">=" and avg_value >= rule.threshold_value:
                violated = True
            elif rule.operator == "<" and avg_value < rule.threshold_value:
                violated = True
            elif rule.operator == "<=" and avg_value <= rule.threshold_value:
                violated = True
            elif rule.operator == "==" and avg_value == rule.threshold_value:
                violated = True
            elif rule.operator == "!=" and avg_value != rule.threshold_value:
                violated = True

            if violated:
                violations.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "metric_name": rule.metric_name,
                    "operator": rule.operator,
                    "threshold_value": rule.threshold_value,
                    "actual_value": round(avg_value, 2),
                    "severity": getattr(rule.severity, "value", rule.severity),
                    "sample_count": len(values),
                })

        return violations

    def get_trend_analysis(
        self,
        test_session_ids: list[int],
        metric: str = "fps",
    ) -> dict:
        results = []
        for session_id in test_session_ids:
            session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
            if not session:
                continue

            samples = (
                self.db.query(PerformanceSample)
                .filter(PerformanceSample.test_session_id == session_id)
                .filter(getattr(PerformanceSample, metric).isnot(None))
                .all()
            )

            if not samples:
                continue

            values = [getattr(s, metric) for s in samples]
            results.append({
                "session_id": session_id,
                "session_name": session.name,
                "mean": float(np.mean(values)),
                "median": float(np.median(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "std": float(np.std(values)),
            })

        return {
            "metric": metric,
            "session_count": len(results),
            "sessions": results,
        }

    def get_full_report(self, test_session_id: int) -> dict:
        session = self.db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not session:
            raise ValueError("测试会话不存在")

        return {
            "session_info": {
                "id": session.id,
                "name": session.name,
                "status": session.status.value if hasattr(session.status, 'value') else session.status,
                "device_model": session.device_model,
                "os_version": session.os_version,
                "xr_runtime": session.xr_runtime,
                "app_version": session.app_version,
                "config": session.config,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "duration_seconds": session.duration_seconds,
            },
            "fps_analysis": self.get_fps_analysis(test_session_id),
            "frame_time_analysis": self.get_frame_time_analysis(test_session_id),
            "memory_analysis": self.get_memory_analysis(test_session_id),
            "thermal_analysis": self.get_thermal_analysis(test_session_id),
            "threshold_violations": self.check_thresholds(test_session_id, session.project_id),
            "stability_summary": self.get_stability_summary(test_session_id),
            "resource_summary": self.get_resource_summary(test_session_id),
            "render_quality_assessment": RenderQualityService(self.db).evaluate_session(test_session_id),
        }

    def get_stability_summary(self, test_session_id: int) -> dict:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .all()
        )
        if not samples:
            return {}

        frame_times = np.array([s.frame_time_ms for s in samples if s.frame_time_ms is not None])
        fps_values = np.array([s.fps for s in samples if s.fps is not None])
        if len(frame_times) == 0:
            return {"sample_count": len(samples)}

        long_frame_threshold_ms = 33.33
        xr_target_frame_ms = 11.11
        long_frames = int(np.sum(frame_times > long_frame_threshold_ms))
        dropped_frames = int(np.sum(frame_times > xr_target_frame_ms * 1.5))
        risk_level = "通过"
        if long_frames > max(3, len(frame_times) * 0.03):
            risk_level = "高风险"
        elif dropped_frames > max(5, len(frame_times) * 0.05):
            risk_level = "需关注"

        return {
            "sample_count": len(samples),
            "avg_fps": float(np.mean(fps_values)) if len(fps_values) else None,
            "p95_frame_time_ms": float(np.percentile(frame_times, 95)),
            "p99_frame_time_ms": float(np.percentile(frame_times, 99)),
            "long_frame_count": long_frames,
            "dropped_frame_count": dropped_frames,
            "dropped_frame_rate": float(dropped_frames / len(frame_times)),
            "risk_level": risk_level,
        }

    def get_resource_summary(self, test_session_id: int) -> dict:
        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .all()
        )
        if not samples:
            return {}

        def avg(values):
            values = [v for v in values if v is not None]
            return float(np.mean(values)) if values else None

        def peak(values):
            values = [v for v in values if v is not None]
            return float(np.max(values)) if values else None

        return {
            "avg_draw_calls": avg([s.draw_calls for s in samples]),
            "avg_set_pass_calls": avg([s.set_pass_calls for s in samples]),
            "avg_triangle_count": avg([s.triangle_count for s in samples]),
            "peak_texture_memory_mb": peak([s.texture_memory_mb for s in samples]),
            "peak_mesh_memory_mb": peak([s.mesh_memory_mb for s in samples]),
            "peak_render_texture_memory_mb": peak([s.render_texture_memory_mb for s in samples]),
            "peak_gc_allocated_mb": peak([s.gc_allocated_mb for s in samples]),
        }
