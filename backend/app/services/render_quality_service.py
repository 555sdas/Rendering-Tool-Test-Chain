from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models.performance_sample import PerformanceSample
from app.models.scene_asset import SceneAsset
from app.models.test_session import TestSession


class RenderQualityService:
    """规则化渲染质量评估。

    该服务输出的是预测试风险分，不是认证分。分数来自可解释阈值扣分：
    已采集到的 Unity/导入指标越完整，可信度越高；没有参考帧或专家复核时，
    光照、材质、后处理和物理仿真只能做辅助评估。
    """

    CATEGORY_WEIGHTS = {
        "lighting": 25,
        "material": 25,
        "post_processing": 25,
        "physics": 25,
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
        enabled_checks = self._enabled_quality_checks(session)
        enabled_metric_checks = self._enabled_quality_metric_checks(session, enabled_checks)
        has_enabled_metrics = {
            key: any(values.values())
            for key, values in enabled_metric_checks.items()
        }
        categories = [
            self._evaluate_lighting(stats, enabled_metric_checks["lighting"]) if enabled_checks["lighting"] and has_enabled_metrics["lighting"] else self._untested_category("lighting", "光照与阴影"),
            self._evaluate_material(stats, enabled_metric_checks["material"]) if enabled_checks["material"] and has_enabled_metrics["material"] else self._untested_category("material", "材质与纹理"),
            self._evaluate_post_processing(stats, enabled_metric_checks["post_processing"]) if enabled_checks["post_processing"] and has_enabled_metrics["post_processing"] else self._untested_category("post_processing", "后处理与画面一致性"),
            self._evaluate_physics(stats, enabled_metric_checks["physics"]) if enabled_checks["physics"] and has_enabled_metrics["physics"] else self._untested_category("physics", "物理仿真与虚实融合"),
        ]
        scored_categories = [c for c in categories if c.get("tested") and c.get("score") is not None]
        total_weight = sum(c["weight"] for c in scored_categories)
        overall = (
            sum(c["score"] * c["weight"] for c in scored_categories) / total_weight
            if total_weight
            else None
        )

        return {
            "session_id": session.id,
            "session_name": session.name,
            "evaluation_mode": self._evaluation_mode(session, samples),
            "overall_score": round(overall, 2) if overall is not None else None,
            "grade": self._grade(overall) if overall is not None else "未测试",
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
                "enabled_quality_metric_checks": enabled_metric_checks,
                "tested_category_count": len(scored_categories),
                "note": "若没有SSIM/PSNR/DeltaE或专家复核输入，本分数只代表预测试风险，不代表最终画质认证。",
            },
        }

    def _enabled_quality_checks(self, session: TestSession) -> dict[str, bool]:
        config = session.config or {}
        raw = config.get("quality_checks") or config.get("qualityChecks")
        if not isinstance(raw, dict):
            return {
                "lighting": True,
                "material": True,
                "post_processing": True,
                "physics": True,
            }

        def enabled(*keys: str) -> bool:
            for key in keys:
                if key in raw:
                    return bool(raw[key])
            return True

        return {
            "lighting": enabled("lighting"),
            "material": enabled("material", "materials"),
            "post_processing": enabled("post_processing", "postProcessing"),
            "physics": enabled("physics"),
        }

    def _enabled_quality_metric_checks(self, session: TestSession, categories: dict[str, bool]) -> dict[str, dict[str, bool]]:
        config = session.config or {}
        raw = config.get("quality_metric_checks") or config.get("qualityMetricChecks")
        if not isinstance(raw, dict):
            raw = {}

        def enabled(category_key: str, *keys: str) -> bool:
            category_enabled = bool(categories.get(category_key, True))
            if not category_enabled:
                return False
            for key in keys:
                if key in raw:
                    return bool(raw[key])
            return True

        return {
            "lighting": {
                "active_lights": enabled("lighting", "lighting.active_lights", "lightingActiveLights"),
                "realtime_lights": enabled("lighting", "lighting.realtime_lights", "lightingRealtimeLights"),
                "shadow_casters": enabled("lighting", "lighting.shadow_casters", "lightingShadowCasters"),
                "reflection_probes": enabled("lighting", "lighting.reflection_probes", "lightingReflectionProbes"),
                "exposure_artifacts": enabled("lighting", "lighting.exposure_artifacts", "lightingExposureArtifacts"),
            },
            "material": {
                "material_slots": enabled("material", "materials.material_slots", "materialSlots"),
                "unique_materials": enabled("material", "materials.unique_materials", "materialUniqueMaterials"),
                "transparent_materials": enabled("material", "materials.transparent_materials", "materialTransparentMaterials"),
                "draw_calls": enabled("material", "materials.draw_calls", "materialDrawCalls"),
                "texture_memory": enabled("material", "materials.texture_memory", "materialTextureMemory"),
            },
            "post_processing": {
                "volumes": enabled("post_processing", "post_processing.volumes", "postProcessVolumes"),
                "render_textures": enabled("post_processing", "post_processing.render_textures", "postProcessRenderTextures"),
                "render_texture_memory": enabled("post_processing", "post_processing.render_texture_memory", "postProcessRenderTextureMemory"),
                "gpu_frame_budget": enabled("post_processing", "post_processing.gpu_frame_budget", "postProcessGpuFrameBudget"),
                "warnings": enabled("post_processing", "post_processing.warnings", "postProcessWarnings"),
            },
            "physics": {
                "rigidbodies": enabled("physics", "physics.rigidbodies", "physicsRigidbodies"),
                "colliders": enabled("physics", "physics.colliders", "physicsColliders"),
                "penetration": enabled("physics", "physics.penetration", "physicsPenetration"),
                "pose_latency": enabled("physics", "physics.pose_latency", "physicsPoseLatency"),
                "prediction_error": enabled("physics", "physics.prediction_error", "physicsPredictionError"),
                "long_frames": enabled("physics", "physics.long_frames", "physicsLongFrames"),
            },
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
            "texture_memory_mb",
            "post_process_volume_count",
            "render_texture_count",
            "render_texture_memory_mb",
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
                if group.get("physics_warning"):
                    flags["physics_warning_count"] += 1

        result: dict[str, Any] = {}
        for name, items in values.items():
            if items:
                result[f"avg_{name}"] = self._mean(items)
                result[f"peak_{name}"] = self._max(items)

        result.update(flags)
        reference_metric_names = {"ssim", "psnr", "delta_e"}
        result["runtime_quality_metrics_present"] = any(
            values[name] for name in metric_names if name not in reference_metric_names
        ) or any(flags.values())
        result["reference_metrics_present"] = any(values[name] for name in ["ssim", "psnr", "delta_e"])
        return result

    def _evaluate_lighting(self, stats: dict[str, Any], enabled: dict[str, bool]) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        light_count = stats.get("peak_active_light_count") or stats.get("scene_light_count")
        shadow_casters = stats.get("peak_shadow_caster_count")
        exposure_delta = stats.get("peak_exposure_delta")

        score = self._deduct(score, deductions, enabled["active_lights"] and light_count is None, 8, "缺少光源数量采集，评分可信度降低")
        score = self._deduct(score, deductions, enabled["active_lights"] and light_count is not None and light_count > 32, 12, "实时光源数量偏高")
        score = self._deduct(score, deductions, enabled["active_lights"] and light_count is not None and light_count > 48, 12, "实时光源数量进入高风险区")
        score = self._deduct(score, deductions, enabled["shadow_casters"] and shadow_casters is not None and shadow_casters > 80, 10, "阴影投射物数量偏高")
        score = self._deduct(score, deductions, enabled["exposure_artifacts"] and exposure_delta is not None and exposure_delta > 0.18, 10, "曝光波动超过建议范围")
        score = self._deduct(score, deductions, enabled["exposure_artifacts"] and stats.get("lighting_flicker_count", 0) > 0, 15, "检测到光照/阴影闪烁标记")
        score = self._deduct(score, deductions, enabled["exposure_artifacts"] and stats.get("overexposure_count", 0) > 0, 8, "存在过曝帧标记")
        score = self._deduct(score, deductions, enabled["exposure_artifacts"] and stats.get("underexposure_count", 0) > 0, 8, "存在欠曝帧标记")
        score = self._deduct(score, deductions, enabled["shadow_casters"] and (stats.get("p95_frame_ms") or 0) > 16.67 and (stats.get("avg_gpu") or 0) > 75, 8, "光照/阴影可能带来GPU帧预算压力")

        if light_count and light_count > 32:
            recommendations.append("合并或烘焙非关键实时光源，优先降低移动端阴影距离和级联数量。")
        if stats.get("lighting_flicker_count", 0):
            recommendations.append("复核水面高光、反射探针和动态阴影，保留关键帧作为人工复核证据。")
        recommendations.append("正式验收建议补充参考帧对比，至少输出SSIM/PSNR/DeltaE中的两类。")

        return self._category(
            "lighting",
            "光照与阴影",
            score,
            {
                "light_count": light_count,
                "realtime_light_count": stats.get("peak_realtime_light_count"),
                "shadow_caster_count": shadow_casters,
                "reflection_probe_count": stats.get("peak_reflection_probe_count"),
                "exposure_delta": exposure_delta,
                "avg_gpu_usage_percent": stats.get("avg_gpu"),
                "p95_frame_time_ms": stats.get("p95_frame_ms"),
                "lighting_flicker_count": stats.get("lighting_flicker_count", 0),
            },
            deductions,
            recommendations,
            [
                self._metric_detail("active_lights", "活动光源数量", light_count, enabled["active_lights"], "统计场景中启用的 Light 数量。"),
                self._metric_detail("realtime_lights", "实时光源数量", stats.get("peak_realtime_light_count"), enabled["realtime_lights"], "识别 Realtime 光源带来的实时光照成本。"),
                self._metric_detail("shadow_casters", "阴影投射数量", shadow_casters, enabled["shadow_casters"], "统计开启阴影投射的 Renderer 数量。"),
                self._metric_detail("reflection_probes", "反射探针数量", stats.get("peak_reflection_probe_count"), enabled["reflection_probes"], "检查 Reflection Probe 规模。"),
                self._metric_detail(
                    "exposure_artifacts",
                    "曝光/闪烁异常",
                    stats.get("peak_exposure_delta") or stats.get("lighting_flicker_count", 0),
                    enabled["exposure_artifacts"],
                    "评估曝光波动、过曝、欠曝和阴影闪烁标记。",
                ),
            ],
        )

    def _evaluate_material(self, stats: dict[str, Any], enabled: dict[str, bool]) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        material_count = stats.get("peak_material_count") or stats.get("scene_texture_count")
        transparent_count = stats.get("peak_transparent_material_count")
        draw_calls = stats.get("avg_draw_calls")
        set_pass = stats.get("avg_set_pass_calls")
        texture_memory = stats.get("peak_texture_memory_mb")

        score = self._deduct(score, deductions, enabled["material_slots"] and material_count is None, 8, "缺少材质/贴图数量采集，评分可信度降低")
        score = self._deduct(score, deductions, enabled["material_slots"] and material_count is not None and material_count > 80, 8, "材质或贴图数量偏高")
        score = self._deduct(score, deductions, enabled["material_slots"] and material_count is not None and material_count > 140, 10, "材质或贴图数量进入高风险区")
        score = self._deduct(score, deductions, enabled["transparent_materials"] and transparent_count is not None and transparent_count > 20, 8, "透明材质数量偏高，可能导致过绘制")
        score = self._deduct(score, deductions, enabled["draw_calls"] and draw_calls is not None and draw_calls > 180, 10, "Draw Call超过V1建议线")
        score = self._deduct(score, deductions, enabled["draw_calls"] and draw_calls is not None and draw_calls > 300, 12, "Draw Call进入高风险区")
        score = self._deduct(score, deductions, enabled["draw_calls"] and set_pass is not None and set_pass > 100, 8, "SetPass Call偏高，材质/Shader切换成本较大")
        score = self._deduct(score, deductions, enabled["texture_memory"] and texture_memory is not None and texture_memory > 1024, 8, "纹理内存超过1GB")
        score = self._deduct(score, deductions, enabled["material_slots"] and stats.get("material_warning_count", 0) > 0, 10, "检测到材质异常标记")

        if draw_calls and draw_calls > 180:
            recommendations.append("检查SRP Batcher、GPU Instancing、静态/动态合批和材质复用。")
        if texture_memory and texture_memory > 1024:
            recommendations.append("复核贴图尺寸、压缩格式、MipMap策略和纹理流送配置。")
        if transparent_count and transparent_count > 20:
            recommendations.append("对透明材质排序、粒子数量和过绘制区域做专项截图复核。")

        return self._category(
            "material",
            "材质与纹理",
            score,
            {
                "material_count": material_count,
                "unique_material_count": stats.get("peak_unique_material_count"),
                "transparent_material_count": transparent_count,
                "avg_draw_calls": draw_calls,
                "avg_set_pass_calls": set_pass,
                "peak_texture_memory_mb": texture_memory,
            },
            deductions,
            recommendations,
            [
                self._metric_detail("material_slots", "材质槽数量", material_count, enabled["material_slots"], "统计 Renderer 绑定的材质槽总量。"),
                self._metric_detail("unique_materials", "唯一材质数量", stats.get("peak_unique_material_count"), enabled["unique_materials"], "评估材质复用和批处理友好度。"),
                self._metric_detail("transparent_materials", "透明材质数量", transparent_count, enabled["transparent_materials"], "定位透明排序和过绘制风险。"),
                self._metric_detail("draw_calls", "Draw Call / SetPass", draw_calls, enabled["draw_calls"], "结合运行时渲染批次评估材质切换成本。"),
                self._metric_detail("texture_memory", "纹理内存", texture_memory, enabled["texture_memory"], "评估贴图尺寸、压缩和纹理流送压力。", "MB"),
            ],
        )

    def _evaluate_post_processing(self, stats: dict[str, Any], enabled: dict[str, bool]) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        volumes = stats.get("peak_post_process_volume_count")
        render_textures = stats.get("peak_render_texture_count")
        rt_memory = stats.get("peak_render_texture_memory_mb")
        gpu = stats.get("avg_gpu")
        p95 = stats.get("p95_frame_ms")

        score = self._deduct(score, deductions, enabled["volumes"] and enabled["render_texture_memory"] and volumes is None and rt_memory is None, 8, "缺少后处理Volume或RenderTexture采集")
        score = self._deduct(score, deductions, enabled["volumes"] and volumes is not None and volumes > 4, 6, "后处理Volume数量偏多")
        score = self._deduct(score, deductions, enabled["render_textures"] and render_textures is not None and render_textures > 12, 8, "RenderTexture数量偏高")
        score = self._deduct(score, deductions, enabled["render_texture_memory"] and rt_memory is not None and rt_memory > 256, 8, "渲染纹理内存超过256MB")
        score = self._deduct(score, deductions, enabled["render_texture_memory"] and rt_memory is not None and rt_memory > 512, 12, "渲染纹理内存进入高风险区")
        score = self._deduct(score, deductions, enabled["gpu_frame_budget"] and gpu is not None and gpu > 85 and p95 is not None and p95 > 16.67, 10, "后处理可能导致GPU帧预算超限")
        score = self._deduct(score, deductions, enabled["warnings"] and stats.get("post_processing_warning_count", 0) > 0, 12, "检测到后处理异常标记")

        if rt_memory and rt_memory > 256:
            recommendations.append("降低全屏后处理分辨率或关闭非必要Bloom、景深、运动模糊。")
        if gpu and gpu > 85:
            recommendations.append("通过图形特性A/B测试量化后处理开关收益。")
        recommendations.append("对亮暗、色彩和抗锯齿问题建议结合截图与参考帧差异图复核。")

        return self._category(
            "post_processing",
            "后处理与画面一致性",
            score,
            {
                "post_process_volume_count": volumes,
                "render_texture_count": render_textures,
                "peak_render_texture_memory_mb": rt_memory,
                "avg_gpu_usage_percent": gpu,
                "p95_frame_time_ms": p95,
            },
            deductions,
            recommendations,
            [
                self._metric_detail("volumes", "Volume 数量", volumes, enabled["volumes"], "统计后处理 Volume 规模。"),
                self._metric_detail("render_textures", "RenderTexture 数量", render_textures, enabled["render_textures"], "统计运行时 RenderTexture 资源数量。"),
                self._metric_detail("render_texture_memory", "渲染纹理内存", rt_memory, enabled["render_texture_memory"], "评估后处理和中间纹理内存压力。", "MB"),
                self._metric_detail("gpu_frame_budget", "GPU 帧预算", gpu, enabled["gpu_frame_budget"], "结合 GPU 占用和 P95 帧时间判断后处理成本。", "%"),
                self._metric_detail("warnings", "后处理异常标记", stats.get("post_processing_warning_count", 0), enabled["warnings"], "接收画面偏色、模糊、抗锯齿等异常标记。"),
            ],
        )

    def _evaluate_physics(self, stats: dict[str, Any], enabled: dict[str, bool]) -> dict[str, Any]:
        score = 100.0
        deductions: list[dict[str, Any]] = []
        recommendations: list[str] = []

        rigidbodies = stats.get("peak_rigidbody_count")
        colliders = stats.get("peak_collider_count")
        penetration = stats.get("peak_penetration_event_count")
        pose_latency = stats.get("avg_pose_latency_ms")
        prediction_error = stats.get("avg_prediction_error_ms")
        long_frames = stats.get("long_frame_count", 0)

        score = self._deduct(score, deductions, enabled["rigidbodies"] and enabled["colliders"] and rigidbodies is None and colliders is None, 8, "缺少刚体/碰撞体采集")
        score = self._deduct(score, deductions, enabled["rigidbodies"] and rigidbodies is not None and rigidbodies > 80, 8, "动态刚体数量偏高")
        score = self._deduct(score, deductions, enabled["colliders"] and colliders is not None and colliders > 250, 8, "碰撞体数量偏高")
        score = self._deduct(score, deductions, enabled["penetration"] and penetration is not None and penetration > 0, 14, "存在穿模/碰撞异常标记")
        score = self._deduct(score, deductions, enabled["pose_latency"] and pose_latency is not None and pose_latency > 20, 8, "姿态/交互延迟超过20ms")
        score = self._deduct(score, deductions, enabled["pose_latency"] and pose_latency is not None and pose_latency > 35, 12, "姿态/交互延迟进入高风险区")
        score = self._deduct(score, deductions, enabled["prediction_error"] and prediction_error is not None and prediction_error > 3, 6, "预测误差偏高")
        score = self._deduct(score, deductions, enabled["long_frames"] and long_frames > 3, 6, "测试中出现多次长帧，需排查物理/动画/脚本峰值")
        score = self._deduct(score, deductions, enabled["penetration"] and stats.get("physics_warning_count", 0) > 0, 12, "检测到物理仿真异常标记")

        if rigidbodies and rigidbodies > 80:
            recommendations.append("降低动态刚体数量，检查碰撞层矩阵、Fixed Timestep和休眠策略。")
        if pose_latency and pose_latency > 20:
            recommendations.append("将交互响应日志与帧时间峰值对齐，确认是否由物理或主线程阻塞引起。")
        recommendations.append("正式虚实融合测试应导入轨迹/空间真值数据，辅助判断漂移、不同步和穿模。")

        return self._category(
            "physics",
            "物理仿真与虚实融合",
            score,
            {
                "rigidbody_count": rigidbodies,
                "collider_count": colliders,
                "penetration_event_count": penetration,
                "avg_pose_latency_ms": pose_latency,
                "avg_prediction_error_ms": prediction_error,
                "long_frame_count": long_frames,
            },
            deductions,
            recommendations,
            [
                self._metric_detail("rigidbodies", "刚体数量", rigidbodies, enabled["rigidbodies"], "统计 Rigidbody 规模和动态物理压力。"),
                self._metric_detail("colliders", "碰撞体数量", colliders, enabled["colliders"], "统计 Collider 数量和碰撞层复杂度。"),
                self._metric_detail("penetration", "穿模/碰撞异常", penetration, enabled["penetration"], "接收穿模、碰撞异常、物理告警标记。"),
                self._metric_detail("pose_latency", "姿态/交互延迟", pose_latency, enabled["pose_latency"], "评估虚实融合交互响应延迟。", "ms"),
                self._metric_detail("prediction_error", "预测误差", prediction_error, enabled["prediction_error"], "评估 XR 姿态预测误差风险。", "ms"),
                self._metric_detail("long_frames", "物理相关长帧", long_frames, enabled["long_frames"], "结合长帧数量排查物理/动画/脚本峰值。"),
            ],
        )

    def _category(
        self,
        key: str,
        name: str,
        score: float,
        metrics: dict[str, Any],
        deductions: list[dict[str, Any]],
        recommendations: list[str],
        metric_details: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        score = max(0.0, min(100.0, score))
        return {
            "key": key,
            "name": name,
            "weight": self.CATEGORY_WEIGHTS[key],
            "score": round(score, 2),
            "tested": True,
            "status": self._status(score),
            "metrics": {k: self._round_metric(v) for k, v in metrics.items()},
            "metric_details": metric_details or [],
            "deductions": deductions,
            "recommendations": recommendations,
        }

    def _untested_category(self, key: str, name: str) -> dict[str, Any]:
        return {
            "key": key,
            "name": name,
            "weight": 0,
            "score": None,
            "tested": False,
            "status": "未测试",
            "metrics": {},
            "metric_details": [],
            "deductions": [],
            "recommendations": ["该维度未在本次任务中勾选，未参与总体质量分计算。"],
        }

    def _metric_detail(
        self,
        key: str,
        label: str,
        value: Any,
        tested: bool,
        description: str,
        unit: str | None = None,
    ) -> dict[str, Any]:
        if not tested:
            return {
                "key": key,
                "label": label,
                "value": None,
                "unit": unit,
                "tested": False,
                "status": "未测试",
                "description": description,
            }
        if value is None:
            status = "缺少数据"
        else:
            status = "已采集"
        return {
            "key": key,
            "label": label,
            "value": self._round_metric(value),
            "unit": unit,
            "tested": True,
            "status": status,
            "description": description,
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
        if isinstance(value, float):
            return round(value, 2)
        return value
