"""测试范围规范化：test_scope 快照、legacy 推断、执行计划与旧字段生成。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import HTTPException, status

from app.services.test_metric_catalog import (
    BASIC_METRIC_IDS,
    METRIC_COLLECTOR_DEPS,
    QUALITY_CATEGORY_IDS,
    QUALITY_METRIC_IDS,
    QUALITY_METRIC_PARENT,
    SCHEMA_VERSION,
    get_catalog_for_api,
    get_default_enabled_quality_metrics,
    get_metric_label,
)


class TestScopeService:
    @staticmethod
    def get_builtin_default_scope(source: str = "built_in_default") -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "basic_metrics": {key: True for key in BASIC_METRIC_IDS},
            "quality_categories": {key: True for key in QUALITY_CATEGORY_IDS},
            "quality_metrics": get_default_enabled_quality_metrics(),
        }

    @classmethod
    def get_catalog(cls) -> dict[str, Any]:
        return get_catalog_for_api()

    @classmethod
    def normalize_scope(
        cls,
        raw_scope: dict[str, Any] | None = None,
        *,
        legacy_fields: dict[str, Any] | None = None,
        source: str = "single_run_override",
    ) -> dict[str, Any]:
        if raw_scope and cls._is_valid_scope_shape(raw_scope):
            scope = cls._fill_scope_keys(raw_scope, source=raw_scope.get("source") or source)
        elif legacy_fields:
            scope = cls._infer_from_legacy(legacy_fields, source=source)
        else:
            scope = cls.get_builtin_default_scope(source=source)

        scope = cls._apply_parent_rules(scope)
        return scope

    @classmethod
    def infer_scope_from_session_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        if not config:
            return cls.get_builtin_default_scope(source="legacy_inferred")

        if isinstance(config.get("test_scope"), dict) and cls._is_valid_scope_shape(config["test_scope"]):
            return cls._fill_scope_keys(config["test_scope"], source=config["test_scope"].get("source") or "session_snapshot")

        legacy = {
            "metric_checks": config.get("metric_checks") or config.get("metricChecks"),
            "quality_checks": config.get("quality_checks") or config.get("qualityChecks"),
            "quality_metric_checks": config.get("quality_metric_checks") or config.get("qualityMetricChecks"),
        }
        if any(legacy.values()):
            return cls._infer_from_legacy(legacy, source="legacy_inferred")
        return cls.get_builtin_default_scope(source="legacy_inferred")

    @classmethod
    def validate_scope(cls, scope: dict[str, Any]) -> None:
        if not cls._has_any_enabled_leaf(scope):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请至少选择一个测试指标",
            )

    @classmethod
    def resolve_execution_plan(cls, scope: dict[str, Any]) -> dict[str, Any]:
        requested_ids = cls._enabled_leaf_ids(scope)
        collector_flags = {
            "frame_rate": False,
            "frame_time": False,
            "cpu": False,
            "gpu": False,
            "memory": False,
            "device_info": False,
            "rendering_stats": False,
            "render_quality": False,
        }
        support_metric_ids: list[str] = []

        def enable_collector(collector: str) -> None:
            if collector in collector_flags:
                collector_flags[collector] = True

        for metric_id in requested_ids:
            deps = METRIC_COLLECTOR_DEPS.get(metric_id, [])
            if metric_id in BASIC_METRIC_IDS:
                enable_collector(metric_id)
            elif metric_id in QUALITY_METRIC_IDS:
                enable_collector("render_quality")
            for dep in deps:
                enable_collector(dep)

        # 依赖支撑：用户未选但为已选规则所需
        for metric_id in requested_ids:
            for dep in METRIC_COLLECTOR_DEPS.get(metric_id, []):
                if dep not in requested_ids and dep in BASIC_METRIC_IDS:
                    support_metric_ids.append(dep)
                    enable_collector(dep)

        # 去重保持顺序
        seen: set[str] = set()
        unique_support = []
        for item in support_metric_ids:
            if item not in seen:
                seen.add(item)
                unique_support.append(item)

        return {
            "schema_version": SCHEMA_VERSION,
            "collector_flags": collector_flags,
            "support_metric_ids": unique_support,
            "requested_metric_ids": requested_ids,
        }

    @classmethod
    def to_legacy_fields(cls, scope: dict[str, Any]) -> dict[str, Any]:
        basic = scope.get("basic_metrics") or {}
        categories = scope.get("quality_categories") or {}
        metrics = scope.get("quality_metrics") or {}

        metric_checks = {key: bool(basic.get(key, False)) for key in BASIC_METRIC_IDS}
        quality_checks = {
            "lighting": bool(categories.get("lighting", False)),
            "materials": bool(categories.get("materials", False)),
            "post_processing": bool(categories.get("post_processing", False)),
            "physics": bool(categories.get("physics", False)),
        }
        quality_metric_checks = {key: bool(metrics.get(key, False)) for key in QUALITY_METRIC_IDS}
        return {
            "metric_checks": metric_checks,
            "quality_checks": quality_checks,
            "quality_metric_checks": quality_metric_checks,
        }

    @classmethod
    def build_scope_summary(cls, scope: dict[str, Any]) -> dict[str, Any]:
        selected_ids = cls._enabled_leaf_ids(scope)
        all_leaf_ids = list(BASIC_METRIC_IDS) + list(QUALITY_METRIC_IDS)
        skipped_ids = [metric_id for metric_id in all_leaf_ids if metric_id not in selected_ids]
        return {
            "selected_ids": selected_ids,
            "skipped_ids": skipped_ids,
            "selected_labels": [get_metric_label(metric_id) for metric_id in selected_ids],
            "skipped_labels": [get_metric_label(metric_id) for metric_id in skipped_ids],
            "selected_count": len(selected_ids),
            "skipped_count": len(skipped_ids),
        }

    @classmethod
    def build_section_status(
        cls,
        scope: dict[str, Any],
        *,
        data_availability: dict[str, bool] | None = None,
    ) -> dict[str, str]:
        """返回基础性能各节的展示状态：selected / skipped / unavailable。"""
        basic = scope.get("basic_metrics") or {}
        availability = data_availability or {}
        result: dict[str, str] = {}
        for metric_id in BASIC_METRIC_IDS:
            if not basic.get(metric_id, False):
                result[metric_id] = "skipped"
            elif availability.get(metric_id) is False:
                result[metric_id] = "unavailable"
            else:
                result[metric_id] = "selected"
        return result

    @classmethod
    def is_metric_enabled(cls, scope: dict[str, Any], metric_id: str) -> bool:
        if metric_id in BASIC_METRIC_IDS:
            return bool((scope.get("basic_metrics") or {}).get(metric_id, False))
        if metric_id in QUALITY_METRIC_IDS:
            parent = QUALITY_METRIC_PARENT[metric_id]
            categories = scope.get("quality_categories") or {}
            metrics = scope.get("quality_metrics") or {}
            return bool(categories.get(parent, False) and metrics.get(metric_id, False))
        if metric_id in QUALITY_CATEGORY_IDS:
            return bool((scope.get("quality_categories") or {}).get(metric_id, False))
        return False

    @classmethod
    def _is_valid_scope_shape(cls, scope: dict[str, Any]) -> bool:
        return any(
            isinstance(scope.get(key), dict)
            for key in ("basic_metrics", "quality_categories", "quality_metrics")
        )

    @classmethod
    def _fill_scope_keys(cls, raw_scope: dict[str, Any], *, source: str) -> dict[str, Any]:
        builtin = cls.get_builtin_default_scope(source=source)
        scope = deepcopy(builtin)
        scope["source"] = source
        scope["schema_version"] = int(raw_scope.get("schema_version") or SCHEMA_VERSION)

        for section, keys in (
            ("basic_metrics", BASIC_METRIC_IDS),
            ("quality_categories", QUALITY_CATEGORY_IDS),
            ("quality_metrics", QUALITY_METRIC_IDS),
        ):
            incoming = raw_scope.get(section) if isinstance(raw_scope.get(section), dict) else {}
            for key in keys:
                if key in incoming:
                    scope[section][key] = bool(incoming[key])
        return scope

    @classmethod
    def _infer_from_legacy(cls, legacy_fields: dict[str, Any], *, source: str) -> dict[str, Any]:
        scope = cls.get_builtin_default_scope(source=source)
        metric_checks = legacy_fields.get("metric_checks") or {}
        quality_checks = legacy_fields.get("quality_checks") or {}
        quality_metric_checks = legacy_fields.get("quality_metric_checks") or {}

        if metric_checks:
            for key in BASIC_METRIC_IDS:
                if key in metric_checks:
                    scope["basic_metrics"][key] = bool(metric_checks[key])

        if quality_checks:
            mapping = {
                "lighting": "lighting",
                "materials": "materials",
                "material": "materials",
                "post_processing": "post_processing",
                "postProcessing": "post_processing",
                "physics": "physics",
            }
            for raw_key, normalized in mapping.items():
                if raw_key in quality_checks:
                    scope["quality_categories"][normalized] = bool(quality_checks[raw_key])

        if quality_metric_checks:
            for key in QUALITY_METRIC_IDS:
                camel = cls._quality_metric_to_camel(key)
                if key in quality_metric_checks:
                    scope["quality_metrics"][key] = bool(quality_metric_checks[key])
                elif camel in quality_metric_checks:
                    scope["quality_metrics"][key] = bool(quality_metric_checks[camel])
        return cls._apply_parent_rules(scope)

    @classmethod
    def _apply_parent_rules(cls, scope: dict[str, Any]) -> dict[str, Any]:
        categories = scope.setdefault("quality_categories", {})
        metrics = scope.setdefault("quality_metrics", {})

        for category_id in QUALITY_CATEGORY_IDS:
            child_keys = [key for key in QUALITY_METRIC_IDS if QUALITY_METRIC_PARENT[key] == category_id]
            if not categories.get(category_id, False):
                for child_key in child_keys:
                    metrics[child_key] = False
                continue
            if child_keys and not any(metrics.get(child_key, False) for child_key in child_keys):
                categories[category_id] = False
                for child_key in child_keys:
                    metrics[child_key] = False
        return scope

    @classmethod
    def _has_any_enabled_leaf(cls, scope: dict[str, Any]) -> bool:
        return bool(cls._enabled_leaf_ids(scope))

    @classmethod
    def _enabled_leaf_ids(cls, scope: dict[str, Any]) -> list[str]:
        enabled: list[str] = []
        basic = scope.get("basic_metrics") or {}
        for metric_id in BASIC_METRIC_IDS:
            if basic.get(metric_id, False):
                enabled.append(metric_id)

        categories = scope.get("quality_categories") or {}
        metrics = scope.get("quality_metrics") or {}
        for metric_id in QUALITY_METRIC_IDS:
            parent = QUALITY_METRIC_PARENT[metric_id]
            if categories.get(parent, False) and metrics.get(metric_id, False):
                enabled.append(metric_id)
        return enabled

    @staticmethod
    def _quality_metric_to_camel(metric_id: str) -> str:
        mapping = {
            "lighting.active_lights": "lightingActiveLights",
            "lighting.realtime_lights": "lightingRealtimeLights",
            "lighting.shadow_casters": "lightingShadowCasters",
            "lighting.reflection_probes": "lightingReflectionProbes",
            "lighting.exposure_artifacts": "lightingExposureArtifacts",
            "materials.material_slots": "materialSlots",
            "materials.unique_materials": "materialUniqueMaterials",
            "materials.transparent_materials": "materialTransparentMaterials",
            "materials.draw_calls": "materialDrawCalls",
            "materials.texture_memory": "materialTextureMemory",
            "post_processing.volumes": "postProcessVolumes",
            "post_processing.render_textures": "postProcessRenderTextures",
            "post_processing.render_texture_memory": "postProcessRenderTextureMemory",
            "post_processing.gpu_frame_budget": "postProcessGpuFrameBudget",
            "post_processing.warnings": "postProcessWarnings",
            "physics.rigidbodies": "physicsRigidbodies",
            "physics.colliders": "physicsColliders",
            "physics.penetration": "physicsPenetration",
            "physics.pose_latency": "physicsPoseLatency",
            "physics.prediction_error": "physicsPredictionError",
            "physics.long_frames": "physicsLongFrames",
        }
        return mapping.get(metric_id, metric_id)
