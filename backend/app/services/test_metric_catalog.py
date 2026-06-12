"""测试指标目录：稳定 ID、中文名、分组、默认值与采集依赖。"""

from __future__ import annotations

from typing import Any, TypedDict


SCHEMA_VERSION = 1


class MetricCatalogEntry(TypedDict, total=False):
    id: str
    label: str
    group: str
    parent_id: str | None
    default_enabled: bool
    capability: str
    requires_collectors: list[str]
    requires_metrics: list[str]
    description: str
    measurement_tier: str
    implementation_status: str
    measurement_semantics: str
    required_capabilities: list[str]
    fallback_policy: str


BASIC_METRIC_IDS = (
    "frame_rate",
    "frame_time",
    "cpu",
    "gpu",
    "memory",
    "device_info",
)

QUALITY_CATEGORY_IDS = (
    "lighting",
    "materials",
    "post_processing",
    "physics",
)

QUALITY_METRIC_IDS = (
    "lighting.active_lights",
    "lighting.realtime_lights",
    "lighting.shadow_casters",
    "lighting.reflection_probes",
    "lighting.exposure_artifacts",
    "materials.material_slots",
    "materials.unique_materials",
    "materials.transparent_materials",
    "materials.draw_calls",
    "materials.texture_memory",
    "post_processing.volumes",
    "post_processing.render_textures",
    "post_processing.render_texture_memory",
    "post_processing.gpu_frame_budget",
    "post_processing.warnings",
    "physics.rigidbodies",
    "physics.colliders",
    "physics.penetration",
    "physics.pose_latency",
    "physics.prediction_error",
    "physics.long_frames",
)

QUALITY_METRIC_PARENT: dict[str, str] = {
    metric_id: metric_id.split(".", 1)[0]
    for metric_id in QUALITY_METRIC_IDS
}

# 用户选择项 → 内部采集器依赖（execution_plan 用）
METRIC_COLLECTOR_DEPS: dict[str, list[str]] = {
    "frame_rate": ["frame_rate"],
    "frame_time": ["frame_time"],
    "cpu": ["cpu"],
    "gpu": ["gpu"],
    "memory": ["memory"],
    "device_info": ["device_info"],
    "materials.draw_calls": ["rendering_stats"],
    "materials.texture_memory": ["memory"],
    "post_processing.gpu_frame_budget": ["gpu", "frame_time"],
    "physics.long_frames": ["frame_time"],
}

# 质量场景计数类指标依赖 render_quality 采集器
RENDER_QUALITY_METRIC_IDS = frozenset(
    metric_id
    for metric_id in QUALITY_METRIC_IDS
    if metric_id not in METRIC_COLLECTOR_DEPS
    or "render_quality" not in METRIC_COLLECTOR_DEPS.get(metric_id, ["render_quality"])
)

COLLECTOR_LABELS = {
    "frame_rate": "帧率采集器",
    "frame_time": "帧时间采集器",
    "cpu": "CPU 采集器",
    "gpu": "GPU 采集器",
    "memory": "内存采集器",
    "device_info": "设备信息采集器",
    "rendering_stats": "渲染统计采集器",
    "render_quality": "渲染质量采集器",
}

METRIC_MEASUREMENT_META: dict[str, dict[str, Any]] = {
    "lighting.active_lights": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "lighting.realtime_lights": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "lighting.shadow_casters": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "lighting.reflection_probes": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "lighting.exposure_artifacts": {
        "measurement_tier": "conditional",
        "implementation_status": "planned",
        "measurement_semantics": "image_analysis",
        "required_capabilities": ["camera"],
        "fallback_policy": "unavailable",
        "default_enabled": False,
    },
    "materials.material_slots": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "materials.unique_materials": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "materials.transparent_materials": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "heuristic_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "materials.draw_calls": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "per_frame_avg",
        "required_capabilities": ["rendering_stats"],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "materials.texture_memory": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "resource_memory_sum",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "post_processing.volumes": {
        "measurement_tier": "conditional",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": ["srp_volume"],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "post_processing.render_textures": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "post_processing.render_texture_memory": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "resource_memory_sum",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "post_processing.gpu_frame_budget": {
        "measurement_tier": "derived",
        "implementation_status": "implemented",
        "measurement_semantics": "derived_gpu_frame_budget",
        "required_capabilities": ["gpu", "frame_time"],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "post_processing.warnings": {
        "measurement_tier": "conditional",
        "implementation_status": "implemented",
        "measurement_semantics": "heuristic_config_audit",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "physics.rigidbodies": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "physics.colliders": {
        "measurement_tier": "native",
        "implementation_status": "implemented",
        "measurement_semantics": "scene_count",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "physics.penetration": {
        "measurement_tier": "conditional",
        "implementation_status": "implemented",
        "measurement_semantics": "heuristic_penetration_scan",
        "required_capabilities": [],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
    "physics.pose_latency": {
        "measurement_tier": "provider_required",
        "implementation_status": "unsupported",
        "measurement_semantics": "xr_timing",
        "required_capabilities": ["xr_pose_timing_provider"],
        "fallback_policy": "unavailable",
        "default_enabled": False,
    },
    "physics.prediction_error": {
        "measurement_tier": "provider_required",
        "implementation_status": "unsupported",
        "measurement_semantics": "xr_prediction",
        "required_capabilities": ["xr_prediction_provider"],
        "fallback_policy": "unavailable",
        "default_enabled": False,
    },
    "physics.long_frames": {
        "measurement_tier": "derived",
        "implementation_status": "implemented",
        "measurement_semantics": "long_frame_proxy",
        "required_capabilities": ["frame_time"],
        "fallback_policy": "unavailable",
        "default_enabled": True,
    },
}

METRIC_DESCRIPTIONS: dict[str, str] = {
    "frame_rate": "每秒渲染的帧数，反映画面流畅度，数值越高通常越流畅。",
    "frame_time": "单帧渲染耗时（毫秒），用于分析卡顿、掉帧与长帧，数值越低越好。",
    "cpu": "CPU 占用百分比，反映脚本逻辑、物理与主线程对性能的影响。",
    "gpu": "GPU 占用与渲染负载，反映着色、绘制与后处理对显卡的压力。",
    "memory": "进程内存占用（含托管堆、显存等），用于发现内存峰值与泄漏风险。",
    "device_info": "采集设备型号、XR 能力、分辨率与渲染管线等测试环境信息。",
    "lighting.active_lights": "统计场景中当前处于启用状态的光源（Light 组件）个数。",
    "lighting.realtime_lights": "统计场景中烘焙模式为「实时光照」且处于启用的光源个数。",
    "lighting.shadow_casters": "统计场景中开启阴影投射的渲染器（Renderer）数量，即会参与生成阴影的物体数。",
    "lighting.reflection_probes": "统计场景中反射探针（Reflection Probe）组件的数量。",
    "lighting.exposure_artifacts": "统计测试过程中出现的曝光相关异常，包括过曝帧、欠曝帧、光照闪烁及曝光波动等标记。",
    "materials.material_slots": "统计场景中所有可见物体挂载的材质槽位总数（同一物体多个材质会计入多次）。",
    "materials.unique_materials": "统计场景中实际使用到的不同材质（Material）资源种类数（按资源去重）。",
    "materials.transparent_materials": "统计场景中被判定为透明/半透明的材质槽位数量（如透明、玻璃、粒子类 Shader）。",
    "materials.draw_calls": "采集测试期间每帧提交给 GPU 的 Draw Call 次数，并汇总为平均值。",
    "materials.texture_memory": "采集测试期间纹理资源占用的内存/显存用量，并记录峰值（MB）。",
    "post_processing.volumes": "统计场景中后处理 Volume 组件数量（用于控制景深、Bloom 等全屏特效的作用范围）。",
    "post_processing.render_textures": "统计场景中 RenderTexture（渲染纹理）资源的数量，常用于离屏渲染与特效。",
    "post_processing.render_texture_memory": "采集测试期间 RenderTexture 占用的内存峰值（MB）。",
    "post_processing.gpu_frame_budget": "根据测试期间的 GPU 占用与帧时间数据，评估渲染是否接近单帧 GPU 时间预算上限。",
    "post_processing.warnings": "审计启用的后处理 Volume 配置，统计缺少共享 Profile 的配置警告数量。",
    "physics.rigidbodies": "统计场景中刚体（Rigidbody）组件的数量。",
    "physics.colliders": "统计场景中碰撞体（Collider）组件的数量。",
    "physics.penetration": "启发式扫描最多 200 个活动非 Trigger 碰撞体，统计实际穿透的碰撞体对数量。",
    "physics.pose_latency": "采集 XR 设备姿态输入到画面更新之间的延迟时间（毫秒），并计算平均值。",
    "physics.prediction_error": "采集姿态预测值与实际姿态之间的误差（毫秒），并计算平均值。",
    "physics.long_frames": "统计测试过程中单帧耗时超过 33ms 的长帧出现次数（物理关联参考，非严格因果归因）。",
}


def get_metric_measurement_meta(metric_id: str) -> dict[str, Any]:
    return dict(METRIC_MEASUREMENT_META.get(metric_id, {}))


def get_default_enabled_quality_metrics() -> dict[str, bool]:
    return {
        metric_id: bool(METRIC_MEASUREMENT_META.get(metric_id, {}).get("default_enabled", True))
        for metric_id in QUALITY_METRIC_IDS
    }


def _basic_entries() -> list[MetricCatalogEntry]:
    labels = {
        "frame_rate": "帧率 FPS",
        "frame_time": "帧时间",
        "cpu": "CPU 使用率",
        "gpu": "GPU 使用率",
        "memory": "内存",
        "device_info": "设备信息",
    }
    return [
        {
            "id": metric_id,
            "label": labels[metric_id],
            "group": "basic_metric",
            "parent_id": None,
            "default_enabled": True,
            "capability": "collect_and_analyze",
            "requires_collectors": METRIC_COLLECTOR_DEPS.get(metric_id, [metric_id]),
            "requires_metrics": [],
            "description": METRIC_DESCRIPTIONS.get(metric_id, ""),
        }
        for metric_id in BASIC_METRIC_IDS
    ]


def _category_entries() -> list[MetricCatalogEntry]:
    labels = {
        "lighting": "光照与阴影",
        "materials": "材质与纹理",
        "post_processing": "后处理",
        "physics": "物理仿真",
    }
    return [
        {
            "id": category_id,
            "label": labels[category_id],
            "group": "quality_category",
            "parent_id": None,
            "default_enabled": True,
            "capability": "analyze",
            "requires_collectors": ["render_quality"],
            "requires_metrics": [],
        }
        for category_id in QUALITY_CATEGORY_IDS
    ]


def _quality_metric_entries() -> list[MetricCatalogEntry]:
    labels = {
        "lighting.active_lights": "活动光源数量",
        "lighting.realtime_lights": "实时光源数量",
        "lighting.shadow_casters": "阴影投射体数量",
        "lighting.reflection_probes": "反射探针数量",
        "lighting.exposure_artifacts": "曝光异常标记",
        "materials.material_slots": "材质槽数量",
        "materials.unique_materials": "去重材质数量",
        "materials.transparent_materials": "透明材质数量",
        "materials.draw_calls": "Draw Call",
        "materials.texture_memory": "纹理内存",
        "post_processing.volumes": "后处理 Volume 数量",
        "post_processing.render_textures": "RenderTexture 数量",
        "post_processing.render_texture_memory": "RenderTexture 内存",
        "post_processing.gpu_frame_budget": "GPU 帧预算压力",
        "post_processing.warnings": "后处理配置警告",
        "physics.rigidbodies": "刚体数量",
        "physics.colliders": "碰撞体数量",
        "physics.penetration": "碰撞体穿透（启发式）",
        "physics.pose_latency": "姿态延迟",
        "physics.prediction_error": "预测误差",
        "physics.long_frames": "测试期间长帧（物理关联参考）",
    }
    entries: list[MetricCatalogEntry] = []
    for metric_id in QUALITY_METRIC_IDS:
        parent_id = QUALITY_METRIC_PARENT[metric_id]
        meta = get_metric_measurement_meta(metric_id)
        collectors = ["render_quality"]
        extra = METRIC_COLLECTOR_DEPS.get(metric_id, [])
        for collector in extra:
            if collector not in collectors:
                collectors.append(collector)
        entries.append(
            {
                "id": metric_id,
                "label": labels[metric_id],
                "group": "quality_metric",
                "parent_id": parent_id,
                "default_enabled": bool(meta.get("default_enabled", True)),
                "capability": "collect_and_analyze",
                "requires_collectors": collectors,
                "requires_metrics": METRIC_COLLECTOR_DEPS.get(metric_id, []),
                "description": METRIC_DESCRIPTIONS.get(
                    metric_id,
                    f"属于「{labels.get(parent_id, parent_id)}」",
                ),
                "measurement_tier": meta.get("measurement_tier"),
                "implementation_status": meta.get("implementation_status"),
                "measurement_semantics": meta.get("measurement_semantics"),
                "required_capabilities": meta.get("required_capabilities", []),
                "fallback_policy": meta.get("fallback_policy"),
            }
        )
    return entries


def get_catalog_entries() -> list[MetricCatalogEntry]:
    return _basic_entries() + _category_entries() + _quality_metric_entries()


def get_catalog_entry(metric_id: str) -> MetricCatalogEntry | None:
    for entry in get_catalog_entries():
        if entry["id"] == metric_id:
            return entry
    return None


def get_catalog_for_api() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "basic_metrics": [e for e in get_catalog_entries() if e["group"] == "basic_metric"],
        "quality_categories": [e for e in get_catalog_entries() if e["group"] == "quality_category"],
        "quality_metrics": [e for e in get_catalog_entries() if e["group"] == "quality_metric"],
        "labels": {
            "basic_metric": "基础性能指标",
            "quality_category": "渲染质量大类",
            "quality_metric": "渲染质量细分指标",
        },
    }


def get_metric_label(metric_id: str) -> str:
    entry = get_catalog_entry(metric_id)
    return entry["label"] if entry else metric_id
