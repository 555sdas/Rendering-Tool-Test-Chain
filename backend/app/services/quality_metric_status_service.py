"""质量子项状态判定：skipped / available / unavailable / missing / failed。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.test_metric_catalog import (
    QUALITY_METRIC_IDS,
    get_metric_measurement_meta,
)
from app.services.test_scope_service import TestScopeService

QualityMetricStatus = str  # skipped | available | unavailable | missing | failed

REASON_LABELS: dict[str, str] = {
    "not_selected": "未纳入本次测试",
    "provider_not_installed": "需要外部 Provider，当前环境未安装",
    "unsupported_render_pipeline": "当前渲染管线不支持该检测",
    "camera_not_available": "无可用 Camera，无法采样",
    "xr_runtime_not_available": "XR 运行时不可用",
    "reference_truth_not_available": "缺少参考真值数据",
    "batchmode_not_supported": "BatchMode 不支持该采集",
    "collector_not_started": "采集器未启动",
    "no_valid_samples": "测试期间无有效样本",
    "collector_exception": "采集过程异常",
    "legacy_plugin_no_manifest": "本次会话未收到插件能力清单；请确认 Unity 已重新编译最新采集插件后重新测试",
    "not_implemented": "通用插件尚未实现该指标采集",
    "derived_dependency_missing": "衍生指标依赖的数据不可用",
}

# scope ID -> (display keys, stats getter returning value or None)
SCOPED_VALUE_BINDINGS: dict[str, list[tuple[str, Callable[[dict[str, Any]], Any]]]] = {
    "lighting.active_lights": [("active_light_count", lambda s: s.get("peak_active_light_count"))],
    "lighting.realtime_lights": [("realtime_light_count", lambda s: s.get("peak_realtime_light_count"))],
    "lighting.shadow_casters": [("shadow_caster_count", lambda s: s.get("peak_shadow_caster_count"))],
    "lighting.reflection_probes": [("reflection_probe_count", lambda s: s.get("peak_reflection_probe_count"))],
    "lighting.exposure_artifacts": [
        ("exposure_delta", lambda s: s.get("peak_exposure_delta")),
        ("overexposure_count", lambda s: s.get("overexposure_count")),
        ("underexposure_count", lambda s: s.get("underexposure_count")),
        ("lighting_flicker_count", lambda s: s.get("lighting_flicker_count")),
    ],
    "materials.material_slots": [
        ("material_count", lambda s: s.get("peak_material_count") or s.get("scene_texture_count")),
    ],
    "materials.unique_materials": [("unique_material_count", lambda s: s.get("peak_unique_material_count"))],
    "materials.transparent_materials": [
        ("transparent_material_count", lambda s: s.get("peak_transparent_material_count")),
    ],
    "materials.draw_calls": [("avg_draw_calls", lambda s: s.get("avg_draw_calls"))],
    "materials.texture_memory": [("peak_texture_memory_mb", lambda s: s.get("peak_texture_memory_mb"))],
    "post_processing.volumes": [
        ("post_process_volume_count", lambda s: s.get("peak_post_process_volume_count")),
    ],
    "post_processing.render_textures": [("render_texture_count", lambda s: s.get("peak_render_texture_count"))],
    "post_processing.render_texture_memory": [
        ("peak_render_texture_memory_mb", lambda s: s.get("peak_render_texture_memory_mb")),
    ],
    "post_processing.gpu_frame_budget": [
        ("avg_gpu_usage_percent", lambda s: s.get("avg_gpu")),
        ("p95_frame_time_ms", lambda s: s.get("p95_frame_ms")),
    ],
    "post_processing.warnings": [
        ("post_processing_warning_count", lambda s: s.get("post_processing_warning_count")),
    ],
    "physics.rigidbodies": [("rigidbody_count", lambda s: s.get("peak_rigidbody_count"))],
    "physics.colliders": [("collider_count", lambda s: s.get("peak_collider_count"))],
    "physics.penetration": [("penetration_event_count", lambda s: s.get("peak_penetration_event_count"))],
    "physics.pose_latency": [("avg_pose_latency_ms", lambda s: s.get("avg_pose_latency_ms"))],
    "physics.prediction_error": [("avg_prediction_error_ms", lambda s: s.get("avg_prediction_error_ms"))],
    "physics.long_frames": [("long_frame_count", lambda s: s.get("long_frame_count"))],
}

# 衍生指标：所有 value key 都有值才算 available
DERIVED_METRIC_IDS = frozenset({"post_processing.gpu_frame_budget", "lighting.exposure_artifacts"})

# 标记类指标：0 也算 available（检测器运行成功）
FLAG_METRIC_VALUE_KEYS = frozenset(
    {
        "overexposure_count",
        "underexposure_count",
        "lighting_flicker_count",
        "post_processing_warning_count",
        "long_frame_count",
    }
)


def _manifest_index(manifest: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not manifest:
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for entry in manifest:
        if isinstance(entry, dict) and entry.get("id"):
            indexed[str(entry["id"])] = entry
    return indexed


def _has_valid_value(value: Any, *, value_key: str) -> bool:
    if value is None:
        return False
    if value_key in FLAG_METRIC_VALUE_KEYS:
        return isinstance(value, (int, float))
    if isinstance(value, (int, float)):
        return True
    return bool(value)


def _collect_values(stats: dict[str, Any], metric_id: str) -> tuple[list[str], list[Any]]:
    bindings = SCOPED_VALUE_BINDINGS.get(metric_id, [])
    keys: list[str] = []
    values: list[Any] = []
    for value_key, getter in bindings:
        keys.append(value_key)
        values.append(getter(stats))
    return keys, values


def _metric_available_from_stats(stats: dict[str, Any], metric_id: str) -> bool:
    keys, values = _collect_values(stats, metric_id)
    if not keys:
        return False
    if metric_id in DERIVED_METRIC_IDS:
        return all(_has_valid_value(value, value_key=key) for key, value in zip(keys, values))
    return any(_has_valid_value(value, value_key=key) for key, value in zip(keys, values))


def build_metric_status_entry(
    metric_id: str,
    scope: dict[str, Any],
    stats: dict[str, Any],
    *,
    manifest: list[dict[str, Any]] | None = None,
    observations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = get_metric_measurement_meta(metric_id)
    manifest_map = _manifest_index(manifest)
    manifest_entry = manifest_map.get(metric_id)
    value_keys, values = _collect_values(stats, metric_id)
    valid_sample_count = 0
    if observations and metric_id in observations:
        valid_sample_count = int(observations[metric_id].get("valid_sample_count") or 0)
    elif manifest_entry:
        valid_sample_count = int(manifest_entry.get("validSampleCount") or manifest_entry.get("valid_sample_count") or 0)

    if not TestScopeService.is_metric_enabled(scope, metric_id):
        return {
            "status": "skipped",
            "reason_code": "not_selected",
            "reason_label": REASON_LABELS["not_selected"],
            "value_keys": value_keys,
            "valid_sample_count": 0,
            "inferred": False,
            "measurement_tier": meta.get("measurement_tier"),
            "implementation_status": meta.get("implementation_status"),
        }

    if manifest_entry:
        status = str(manifest_entry.get("status") or "missing")
        reason_code = manifest_entry.get("reasonCode") or manifest_entry.get("reason_code")
        inferred = False
        if status == "available":
            if _metric_available_from_stats(stats, metric_id):
                status = "available"
            else:
                status = "missing"
                reason_code = reason_code or "no_valid_samples"
        return {
            "status": status,
            "reason_code": reason_code,
            "reason_label": REASON_LABELS.get(str(reason_code), str(reason_code) if reason_code else None),
            "value_keys": value_keys,
            "valid_sample_count": valid_sample_count,
            "inferred": inferred,
            "measurement_tier": manifest_entry.get("measurementTier") or meta.get("measurement_tier"),
            "implementation_status": meta.get("implementation_status"),
            "provider": manifest_entry.get("provider"),
        }

    # 旧会话 / 无 manifest：推断
    impl = meta.get("implementation_status", "implemented")
    if impl in {"unsupported", "planned"}:
        return {
            "status": "unavailable",
            "reason_code": "not_implemented" if impl == "planned" else "provider_not_installed",
            "reason_label": REASON_LABELS["not_implemented"]
            if impl == "planned"
            else REASON_LABELS["provider_not_installed"],
            "value_keys": value_keys,
            "valid_sample_count": 0,
            "inferred": True,
            "measurement_tier": meta.get("measurement_tier"),
            "implementation_status": impl,
        }

    if _metric_available_from_stats(stats, metric_id):
        return {
            "status": "available",
            "reason_code": None,
            "reason_label": None,
            "value_keys": value_keys,
            "valid_sample_count": valid_sample_count,
            "inferred": True,
            "measurement_tier": meta.get("measurement_tier"),
            "implementation_status": impl,
        }

    return {
        "status": "missing",
        "reason_code": "legacy_plugin_no_manifest",
        "reason_label": REASON_LABELS["legacy_plugin_no_manifest"],
        "value_keys": value_keys,
        "valid_sample_count": 0,
        "inferred": True,
        "measurement_tier": meta.get("measurement_tier"),
        "implementation_status": impl,
    }


def build_all_metric_status(
    scope: dict[str, Any],
    stats: dict[str, Any],
    *,
    manifest: list[dict[str, Any]] | None = None,
    observations: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        metric_id: build_metric_status_entry(
            metric_id,
            scope,
            stats,
            manifest=manifest,
            observations=observations,
        )
        for metric_id in QUALITY_METRIC_IDS
    }


def summarize_coverage(metric_status: dict[str, dict[str, Any]], scope: dict[str, Any]) -> dict[str, int]:
    counts = {"selected": 0, "available": 0, "unavailable": 0, "missing": 0, "failed": 0, "skipped": 0}
    for metric_id in QUALITY_METRIC_IDS:
        if not TestScopeService.is_metric_enabled(scope, metric_id):
            counts["skipped"] += 1
            continue
        counts["selected"] += 1
        status = metric_status.get(metric_id, {}).get("status", "missing")
        if status in counts:
            counts[status] += 1
    return counts


def compute_data_completeness(coverage: dict[str, int]) -> float | None:
    selected = coverage.get("selected", 0)
    if selected <= 0:
        return None
    available = coverage.get("available", 0)
    return round(available / selected, 4)


def confidence_grade_from_completeness(completeness: float | None) -> str:
    if completeness is None:
        return "未评估"
    if completeness >= 0.9:
        return "A"
    if completeness >= 0.75:
        return "B"
    if completeness >= 0.5:
        return "C"
    return "D"


def category_metric_status(
    category_parent: str,
    all_status: dict[str, dict[str, Any]],
    scope: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    subset = {
        metric_id: status
        for metric_id, status in all_status.items()
        if metric_id.startswith(f"{category_parent}.")
    }
    counts = {"selected": 0, "available": 0, "unavailable": 0, "missing": 0, "failed": 0, "skipped": 0}
    for metric_id in subset:
        if not TestScopeService.is_metric_enabled(scope, metric_id):
            counts["skipped"] += 1
            continue
        counts["selected"] += 1
        status = subset[metric_id].get("status", "missing")
        if status in counts:
            counts[status] += 1
    return subset, counts
