from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models.performance_sample import PerformanceSample
from app.models.scene_asset import SceneAsset
from app.models.test_session import TestSession
from app.services.quality_metric_status_service import (
    SCOPED_VALUE_BINDINGS,
    build_all_metric_status,
    category_metric_status,
    compute_data_completeness,
    confidence_grade_from_completeness,
    summarize_coverage,
)
from app.services.scoring_definition_service import ScoringDefinitionService, WEIGHT_SUM_TOLERANCE
from app.services.test_metric_catalog import QUALITY_METRIC_IDS
from app.services.test_scope_service import TestScopeService


class RenderQualityService:
    """规则化渲染质量评估。

    该服务输出的是预测试风险分，不是认证分。分数来自可解释阈值扣分：
    已采集到的 Unity/导入指标越完整，可信度越高；没有参考帧或专家复核时，
    光照、材质、后处理和物理仿真只能做辅助评估。
    """

    CATEGORY_PARENT = {
        "lighting": "lighting",
        "material": "materials",
        "post_processing": "post_processing",
        "physics": "physics",
    }

    def __init__(self, db: Session):
        self.db = db

    def evaluate_session(self, test_session_id: int) -> dict[str, Any]:
        session = self.db.query(TestSession).filter(TestSession.id == test_session_id).first()
        if not session:
            raise ValueError("测试会话不存在")

        samples = (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .all()
        )
        scene = None
        if session.scene_id:
            scene = self.db.query(SceneAsset).filter(SceneAsset.id == session.scene_id).first()

        stats = self._build_stats(samples, scene)
        session_config = session.config or {}
        scope = TestScopeService.infer_scope_from_session_config(session_config)
        manifest = session_config.get("quality_metric_manifest") or session_config.get("qualityMetricManifest")
        all_metric_status = build_all_metric_status(scope, stats, manifest=manifest)
        coverage_summary = summarize_coverage(all_metric_status, scope)
        data_completeness = compute_data_completeness(coverage_summary)
        confidence_grade = confidence_grade_from_completeness(data_completeness)
        enabled_checks = self._enabled_quality_checks(session, scope)
        scope_summary = TestScopeService.build_scope_summary(scope)
        enabled_metric_ids = [
            metric_id for metric_id in QUALITY_METRIC_IDS if TestScopeService.is_metric_enabled(scope, metric_id)
        ]
        skipped_metric_ids = [
            metric_id for metric_id in QUALITY_METRIC_IDS if metric_id not in enabled_metric_ids
        ]
        scoring_resolved = ScoringDefinitionService.resolve_session_definition(session_config)
        scoring_definition = scoring_resolved["definition"]
        category_weights = scoring_definition["category_weights"]
        categories = [
            self._evaluate_lighting(stats, scope, all_metric_status, category_weights["lighting"])
            if enabled_checks["lighting"]
            else self._untested_category("lighting", "光照与阴影", category_weights["lighting"]),
            self._evaluate_material(stats, scope, all_metric_status, category_weights["material"])
            if enabled_checks["material"]
            else self._untested_category("material", "材质与纹理", category_weights["material"]),
            self._evaluate_post_processing(stats, scope, all_metric_status, category_weights["post_processing"])
            if enabled_checks["post_processing"]
            else self._untested_category("post_processing", "后处理与画面一致性", category_weights["post_processing"]),
            self._evaluate_physics(stats, scope, all_metric_status, category_weights["physics"])
            if enabled_checks["physics"]
            else self._untested_category("physics", "物理仿真与虚实融合", category_weights["physics"]),
        ]
        scored_categories = [
            c
            for c in categories
            if c.get("tested") and c.get("score") is not None and c.get("included_in_overall_score")
        ]
        total_weight = sum(c["weight"] for c in scored_categories)
        overall = (
            sum(c["score"] * c["weight"] for c in scored_categories) / total_weight
            if total_weight
            else None
        )
        overall_score_reason = None
        tested_scored = [c for c in categories if c.get("tested") and c.get("score") is not None]
        if tested_scored and not scored_categories:
            overall_score_reason = "所有参与测试分类的配置权重均为 0，无法计算总分"

        included_category_keys = [c["key"] for c in scored_categories]
        score_formula = {
            "effective_total_weight": round(total_weight, 4) if total_weight else 0,
            "included_categories": included_category_keys,
            "normalized": bool(total_weight and abs(total_weight - 100.0) > WEIGHT_SUM_TOLERANCE),
        }

        return {
            "session_id": session.id,
            "session_name": session.name,
            "evaluation_mode": self._evaluation_mode(session, samples),
            "overall_score": round(overall, 2) if overall is not None else None,
            "overall_score_reason": overall_score_reason,
            "grade": self._grade(overall) if overall is not None else "未测试",
            "scoring_definition": scoring_definition,
            "scoring_definition_source": scoring_resolved["source"],
            "scoring_definition_fallback_reason": scoring_resolved["fallback_reason"],
            "score_formula": score_formula,
            "data_completeness": data_completeness,
            "confidence_grade": confidence_grade,
            "coverage_summary": coverage_summary,
            "metric_status": all_metric_status,
            "categories": categories,
            "rubric": {
                "lighting": "光源/阴影复杂度、曝光异常、光照闪烁、GPU与长帧风险。",
                "material": "Draw Call、SetPass、材质/透明材质数量、纹理内存和材质复用风险。",
                "post_processing": "RenderTexture内存、后处理Volume数量、GPU压力和后处理缺陷标记。",
                "physics": "刚体/碰撞体规模、穿模/碰撞异常、姿态延迟、预测误差和物理导致长帧。",
            },
            "evidence": {
                "sample_count": len(samples),
                "scene_asset": scene.name if scene else None,
                "has_reference_frame_metrics": bool(stats["reference_metrics_present"]),
                "has_runtime_quality_metrics": bool(stats["runtime_quality_metrics_present"]),
                "enabled_quality_checks": enabled_checks,
                "enabled_metric_ids": enabled_metric_ids,
                "skipped_metric_ids": skipped_metric_ids,
                "test_scope_source": scope.get("source"),
                "tested_category_count": len(scored_categories),
                "note": "若没有SSIM/PSNR/DeltaE或专家复核输入，本分数只代表预测试风险，不代表最终画质认证。",
                "data_completeness": data_completeness,
                "confidence_grade": confidence_grade,
                "coverage_summary": coverage_summary,
                "has_quality_metric_manifest": bool(manifest),
            },
            "test_scope": scope,
            "test_scope_summary": scope_summary,
        }

    def _enabled_quality_checks(self, session: TestSession, scope: dict[str, Any] | None = None) -> dict[str, bool]:
        scope = scope or TestScopeService.infer_scope_from_session_config(session.config or {})
        categories = scope.get("quality_categories") or {}
        return {
            "lighting": bool(categories.get("lighting", False)),
            "material": bool(categories.get("materials", False)),
            "post_processing": bool(categories.get("post_processing", False)),
            "physics": bool(categories.get("physics", False)),
        }

    def _build_stats(self, samples: list[PerformanceSample], scene: SceneAsset | None) -> dict[str, Any]:
        frame_times = self._values(samples, "frame_time_ms")
        fps_values = self._values(samples, "fps")

        stats: dict[str, Any] = {
            "sample_count": len(samples),
            "avg_fps": self._mean(fps_values),
            "avg_gpu": self._mean(self._values(samples, "gpu_usage_percent")),
            "p95_frame_ms": self._percentile(frame_times, 95),
            "long_frame_count": int(np.sum(np.array(frame_times) > 33.33)) if frame_times else 0,
            "dropped_frame_rate": self._dropped_frame_rate(frame_times),
            "avg_draw_calls": self._mean(self._values(samples, "draw_calls")),
            "avg_set_pass_calls": self._mean(self._values(samples, "set_pass_calls")),
            "avg_triangles": self._mean(self._values(samples, "triangle_count")),
            "peak_texture_memory_mb": self._max(self._values(samples, "texture_memory_mb")),
            "peak_render_texture_memory_mb": self._max(self._values(samples, "render_texture_memory_mb")),
            "avg_pose_latency_ms": self._mean(self._values(samples, "pose_latency_ms")),
            "avg_prediction_error_ms": self._mean(self._values(samples, "prediction_error_ms")),
            "scene_light_count": scene.light_count if scene else None,
            "scene_texture_count": scene.texture_count if scene else None,
            "scene_particle_count": scene.particle_count if scene else None,
            "scene_complexity_score": scene.complexity_score if scene else None,
            "runtime_quality_metrics_present": False,
            "reference_metrics_present": False,
        }

        stats.update(self._collect_extra_quality_metrics(samples))
        return stats

    def _collect_extra_quality_metrics(self, samples: list[PerformanceSample]) -> dict[str, Any]:
        metric_names = [
            "active_light_count",
            "realtime_light_count",
            "shadow_caster_count",
            "reflection_probe_count",
            "material_count",
            "unique_material_count",
            "transparent_material_count",
            "post_process_volume_count",
            "render_texture_count",
            "rigidbody_count",
            "collider_count",
            "penetration_event_count",
            "physics_warning_count",
            "exposure_delta",
            "ssim",
            "psnr",
            "delta_e",
        ]
        values: dict[str, list[float]] = {name: [] for name in metric_names}
        flags = {
            "lighting_flicker_count": 0,
            "overexposure_count": 0,
            "underexposure_count": 0,
            "shadow_artifact_count": 0,
            "material_warning_count": 0,
            "post_processing_warning_count": 0,
            "physics_warning_count": 0,
        }

        for sample in samples:
            extra = sample.extra_metrics or {}
            quality = extra.get("render_quality") or extra.get("quality") or {}
            if not isinstance(quality, dict):
                continue

            groups = [
                quality,
                quality.get("lighting", {}),
                quality.get("material", {}),
                quality.get("materials", {}),
                quality.get("post_processing", {}),
                quality.get("physics", {}),
                quality.get("reference_frame", {}),
            ]
            for group in groups:
                if not isinstance(group, dict):
                    continue
                for name in metric_names:
                    value = group.get(name)
                    if isinstance(value, (int, float)) and value >= 0:
                        values[name].append(float(value))

                if group.get("lighting_flicker") or group.get("shadow_flicker"):
                    flags["lighting_flicker_count"] += 1
                if group.get("overexposure"):
                    flags["overexposure_count"] += 1
                if group.get("underexposure"):
                    flags["underexposure_count"] += 1
                if group.get("shadow_artifact"):
                    flags["shadow_artifact_count"] += 1
                if group.get("material_warning"):
                    flags["material_warning_count"] += 1
                if group.get("post_processing_warning"):
                    flags["post_processing_warning_count"] += 1
                numeric_post_warnings = group.get("post_processing_warning_count")
                if isinstance(numeric_post_warnings, (int, float)) and numeric_post_warnings >= 0:
                    flags["post_processing_warning_count"] = max(
                        flags["post_processing_warning_count"],
                        int(numeric_post_warnings),
                    )
                if group.get("physics_warning"):
                    flags["physics_warning_count"] += 1

        result: dict[str, Any] = {}
        for name, items in values.items():
            if items:
                result[f"avg_{name}"] = self._mean(items)
                result[f"peak_{name}"] = self._max(items)

        result.update(flags)
        result["runtime_quality_metrics_present"] = any(values[name] for name in metric_names[:14]) or any(flags.values())
        result["reference_metrics_present"] = any(values[name] for name in ["ssim", "psnr", "delta_e"])
        return result

    @staticmethod
    def _metric_is_available(metric_status: dict[str, dict[str, Any]], metric_id: str) -> bool:
        return metric_status.get(metric_id, {}).get("status") == "available"

    def _build_scoped_category_metrics(self, category_key: str, stats: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
        parent = self.CATEGORY_PARENT[category_key]
        metrics: dict[str, Any] = {}
        for scope_id, bindings in SCOPED_VALUE_BINDINGS.items():
            if not scope_id.startswith(f"{parent}."):
                continue
            if not TestScopeService.is_metric_enabled(scope, scope_id):
                continue
            for display_key, getter in bindings:
                if display_key in metrics:
                    continue
                metrics[display_key] = getter(stats)
        return metrics

    def _evaluate_lighting(
        self,
        stats: dict[str, Any],
        scope: dict[str, Any],
        metric_status: dict[str, dict[str, Any]],
        category_weight: float,
    ) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        light_count = stats.get("peak_active_light_count") or stats.get("scene_light_count")
        shadow_casters = stats.get("peak_shadow_caster_count")
        exposure_delta = stats.get("peak_exposure_delta")

        if TestScopeService.is_metric_enabled(scope, "lighting.active_lights"):
            score = self._deduct(score, deductions, light_count is None, 8, "缺少光源数量采集，评分可信度降低")
            score = self._deduct(score, deductions, light_count is not None and light_count > 32, 12, "实时光源数量偏高")
            score = self._deduct(score, deductions, light_count is not None and light_count > 48, 12, "实时光源数量进入高风险区")
        if self._metric_is_available(metric_status, "lighting.shadow_casters"):
            score = self._deduct(score, deductions, shadow_casters is not None and shadow_casters > 80, 10, "阴影投射物数量偏高")
        if self._metric_is_available(metric_status, "lighting.exposure_artifacts"):
            score = self._deduct(score, deductions, exposure_delta is not None and exposure_delta > 0.18, 10, "曝光波动超过建议范围")
            score = self._deduct(score, deductions, stats.get("lighting_flicker_count", 0) > 0, 15, "检测到光照/阴影闪烁标记")
            score = self._deduct(score, deductions, stats.get("overexposure_count", 0) > 0, 8, "存在过曝帧标记")
            score = self._deduct(score, deductions, stats.get("underexposure_count", 0) > 0, 8, "存在欠曝帧标记")

        if light_count and light_count > 32:
            recommendations.append("合并或烘焙非关键实时光源，优先降低移动端阴影距离和级联数量。")
        if stats.get("lighting_flicker_count", 0):
            recommendations.append("复核水面高光、反射探针和动态阴影，保留关键帧作为人工复核证据。")
        recommendations.append("正式验收建议补充参考帧对比，至少输出SSIM/PSNR/DeltaE中的两类。")

        cat_status, cat_coverage = category_metric_status("lighting", metric_status, scope)
        return self._category(
            "lighting",
            "光照与阴影",
            score,
            self._build_scoped_category_metrics("lighting", stats, scope),
            deductions,
            recommendations,
            weight=category_weight,
            metric_status=cat_status,
            coverage=cat_coverage,
        )

    def _evaluate_material(
        self,
        stats: dict[str, Any],
        scope: dict[str, Any],
        metric_status: dict[str, dict[str, Any]],
        category_weight: float,
    ) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        material_count = stats.get("peak_material_count") or stats.get("scene_texture_count")
        transparent_count = stats.get("peak_transparent_material_count")
        draw_calls = stats.get("avg_draw_calls")
        set_pass = stats.get("avg_set_pass_calls")
        texture_memory = stats.get("peak_texture_memory_mb")

        if TestScopeService.is_metric_enabled(scope, "materials.material_slots"):
            score = self._deduct(score, deductions, material_count is None, 8, "缺少材质/贴图数量采集，评分可信度降低")
            score = self._deduct(score, deductions, material_count is not None and material_count > 80, 8, "材质或贴图数量偏高")
            score = self._deduct(score, deductions, material_count is not None and material_count > 140, 10, "材质或贴图数量进入高风险区")
        if self._metric_is_available(metric_status, "materials.transparent_materials"):
            score = self._deduct(score, deductions, transparent_count is not None and transparent_count > 20, 8, "透明材质数量偏高，可能导致过绘制")
        if self._metric_is_available(metric_status, "materials.draw_calls"):
            score = self._deduct(score, deductions, draw_calls is not None and draw_calls > 180, 10, "Draw Call超过V1建议线")
            score = self._deduct(score, deductions, draw_calls is not None and draw_calls > 300, 12, "Draw Call进入高风险区")
        score = self._deduct(score, deductions, set_pass is not None and set_pass > 100, 8, "SetPass Call偏高，材质/Shader切换成本较大")
        if self._metric_is_available(metric_status, "materials.texture_memory"):
            score = self._deduct(score, deductions, texture_memory is not None and texture_memory > 1024, 8, "纹理内存超过1GB")
        score = self._deduct(score, deductions, stats.get("material_warning_count", 0) > 0, 10, "检测到材质异常标记")

        if draw_calls and draw_calls > 180:
            recommendations.append("检查SRP Batcher、GPU Instancing、静态/动态合批和材质复用。")
        if texture_memory and texture_memory > 1024:
            recommendations.append("复核贴图尺寸、压缩格式、MipMap策略和纹理流送配置。")
        if transparent_count and transparent_count > 20:
            recommendations.append("对透明材质排序、粒子数量和过绘制区域做专项截图复核。")

        cat_status, cat_coverage = category_metric_status("materials", metric_status, scope)
        return self._category(
            "material",
            "材质与纹理",
            score,
            self._build_scoped_category_metrics("material", stats, scope),
            deductions,
            recommendations,
            weight=category_weight,
            metric_status=cat_status,
            coverage=cat_coverage,
        )

    def _evaluate_post_processing(
        self,
        stats: dict[str, Any],
        scope: dict[str, Any],
        metric_status: dict[str, dict[str, Any]],
        category_weight: float,
    ) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        volumes = stats.get("peak_post_process_volume_count")
        render_textures = stats.get("peak_render_texture_count")
        rt_memory = stats.get("peak_render_texture_memory_mb")
        gpu = stats.get("avg_gpu")
        p95 = stats.get("p95_frame_ms")

        if TestScopeService.is_metric_enabled(scope, "post_processing.volumes") or TestScopeService.is_metric_enabled(
            scope, "post_processing.render_texture_memory"
        ):
            score = self._deduct(score, deductions, volumes is None and rt_memory is None, 8, "缺少后处理Volume或RenderTexture采集")
        if self._metric_is_available(metric_status, "post_processing.volumes"):
            score = self._deduct(score, deductions, volumes is not None and volumes > 4, 6, "后处理Volume数量偏多")
        if self._metric_is_available(metric_status, "post_processing.render_textures"):
            score = self._deduct(score, deductions, render_textures is not None and render_textures > 12, 8, "RenderTexture数量偏高")
        if self._metric_is_available(metric_status, "post_processing.render_texture_memory"):
            score = self._deduct(score, deductions, rt_memory is not None and rt_memory > 256, 8, "渲染纹理内存超过256MB")
            score = self._deduct(score, deductions, rt_memory is not None and rt_memory > 512, 12, "渲染纹理内存进入高风险区")
        if self._metric_is_available(metric_status, "post_processing.gpu_frame_budget"):
            score = self._deduct(score, deductions, gpu is not None and gpu > 85 and p95 is not None and p95 > 16.67, 10, "后处理可能导致GPU帧预算超限")
        if self._metric_is_available(metric_status, "post_processing.warnings"):
            score = self._deduct(score, deductions, stats.get("post_processing_warning_count", 0) > 0, 12, "检测到后处理异常标记")

        if rt_memory and rt_memory > 256:
            recommendations.append("降低全屏后处理分辨率或关闭非必要Bloom、景深、运动模糊。")
        if gpu and gpu > 85:
            recommendations.append("通过图形特性A/B测试量化后处理开关收益。")
        recommendations.append("对亮暗、色彩和抗锯齿问题建议结合截图与参考帧差异图复核。")

        cat_status, cat_coverage = category_metric_status("post_processing", metric_status, scope)
        return self._category(
            "post_processing",
            "后处理与画面一致性",
            score,
            self._build_scoped_category_metrics("post_processing", stats, scope),
            deductions,
            recommendations,
            weight=category_weight,
            metric_status=cat_status,
            coverage=cat_coverage,
        )

    def _evaluate_physics(
        self,
        stats: dict[str, Any],
        scope: dict[str, Any],
        metric_status: dict[str, dict[str, Any]],
        category_weight: float,
    ) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        rigidbodies = stats.get("peak_rigidbody_count")
        colliders = stats.get("peak_collider_count")
        penetration = stats.get("peak_penetration_event_count")
        pose_latency = stats.get("avg_pose_latency_ms")
        prediction_error = stats.get("avg_prediction_error_ms")
        long_frames = stats.get("long_frame_count", 0)

        if TestScopeService.is_metric_enabled(scope, "physics.rigidbodies") or TestScopeService.is_metric_enabled(
            scope, "physics.colliders"
        ):
            score = self._deduct(score, deductions, rigidbodies is None and colliders is None, 8, "缺少刚体/碰撞体采集")
        if self._metric_is_available(metric_status, "physics.rigidbodies"):
            score = self._deduct(score, deductions, rigidbodies is not None and rigidbodies > 80, 8, "动态刚体数量偏高")
        if self._metric_is_available(metric_status, "physics.colliders"):
            score = self._deduct(score, deductions, colliders is not None and colliders > 250, 8, "碰撞体数量偏高")
        if self._metric_is_available(metric_status, "physics.penetration"):
            score = self._deduct(score, deductions, penetration is not None and penetration > 0, 14, "存在穿模/碰撞异常标记")
        if self._metric_is_available(metric_status, "physics.pose_latency"):
            score = self._deduct(score, deductions, pose_latency is not None and pose_latency > 20, 8, "姿态/交互延迟超过20ms")
            score = self._deduct(score, deductions, pose_latency is not None and pose_latency > 35, 12, "姿态/交互延迟进入高风险区")
        if self._metric_is_available(metric_status, "physics.prediction_error"):
            score = self._deduct(score, deductions, prediction_error is not None and prediction_error > 3, 6, "预测误差偏高")
        if self._metric_is_available(metric_status, "physics.long_frames"):
            score = self._deduct(score, deductions, long_frames > 3, 6, "测试中出现多次长帧，需排查物理/动画/脚本峰值")
        score = self._deduct(score, deductions, stats.get("physics_warning_count", 0) > 0, 12, "检测到物理仿真异常标记")

        if rigidbodies and rigidbodies > 80:
            recommendations.append("降低动态刚体数量，检查碰撞层矩阵、Fixed Timestep和休眠策略。")
        if pose_latency and pose_latency > 20:
            recommendations.append("将交互响应日志与帧时间峰值对齐，确认是否由物理或主线程阻塞引起。")
        recommendations.append("正式虚实融合测试应导入轨迹/空间真值数据，辅助判断漂移、不同步和穿模。")

        cat_status, cat_coverage = category_metric_status("physics", metric_status, scope)
        return self._category(
            "physics",
            "物理仿真与虚实融合",
            score,
            self._build_scoped_category_metrics("physics", stats, scope),
            deductions,
            recommendations,
            weight=category_weight,
            metric_status=cat_status,
            coverage=cat_coverage,
        )

    def _category(
        self,
        key: str,
        name: str,
        score: float,
        metrics: dict[str, Any],
        deductions: list[dict[str, Any]],
        recommendations: list[str],
        *,
        weight: float,
        metric_status: dict[str, dict[str, Any]] | None = None,
        coverage: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        score = max(0.0, min(100.0, score))
        included = weight > 0
        return {
            "key": key,
            "name": name,
            "weight": round(weight, 4),
            "included_in_overall_score": included,
            "score": round(score, 2),
            "tested": True,
            "status": self._status(score),
            "metrics": {k: self._round_metric(v) for k, v in metrics.items()},
            "metric_status": metric_status or {},
            "coverage": coverage or {},
            "deductions": deductions,
            "recommendations": recommendations,
        }

    def _untested_category(self, key: str, name: str, weight: float) -> dict[str, Any]:
        return {
            "key": key,
            "name": name,
            "weight": round(weight, 4),
            "included_in_overall_score": False,
            "score": None,
            "tested": False,
            "status": "未测试",
            "metrics": {},
            "metric_status": {},
            "coverage": {},
            "deductions": [],
            "recommendations": ["该维度未在本次任务中勾选，未参与总体质量分计算。"],
        }

    def _evaluation_mode(self, session: TestSession, samples: list[PerformanceSample]) -> dict[str, str]:
        config = session.config or {}
        test_platform = str(config.get("test_platform", ""))
        has_quality = any((s.extra_metrics or {}).get("render_quality") for s in samples)
        if "synthetic" in test_platform.lower():
            return {
                "type": "deterministic_demo",
                "description": "当前会话包含确定性演示数据，评分公式真实可解释，但不是BoatAttack画面的正式实测认证结论。",
            }
        if has_quality:
            return {
                "type": "metric_rule_based",
                "description": "基于采集/导入的运行指标、场景指标和缺陷标记计算预测试风险分。",
            }
        return {
            "type": "inferred_from_performance",
            "description": "缺少专项视觉质量指标，当前只依据性能与资源字段进行保守推断。",
        }

    def _values(self, samples: list[PerformanceSample], field: str) -> list[float]:
        values = []
        for sample in samples:
            value = getattr(sample, field, None)
            if isinstance(value, (int, float)):
                values.append(float(value))
        return values

    def _mean(self, values: list[float] | None) -> float | None:
        return float(np.mean(values)) if values else None

    def _max(self, values: list[float] | None) -> float | None:
        return float(np.max(values)) if values else None

    def _percentile(self, values: list[float] | None, percentile: int) -> float | None:
        return float(np.percentile(values, percentile)) if values else None

    def _dropped_frame_rate(self, frame_times: list[float]) -> float | None:
        if not frame_times:
            return None
        target_frame_ms = 11.11
        dropped = np.sum(np.array(frame_times) > target_frame_ms * 1.5)
        return float(dropped / len(frame_times))

    def _deduct(
        self,
        score: float,
        deductions: list[dict[str, Any]],
        condition: bool,
        points: float,
        reason: str,
    ) -> float:
        if condition:
            deductions.append({"points": points, "reason": reason})
            return score - points
        return score

    def _status(self, score: float) -> str:
        if score >= 85:
            return "通过"
        if score >= 70:
            return "需关注"
        return "高风险"

    def _grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        return "D"

    def _round_metric(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float):
            return round(value, 2)
        return value
