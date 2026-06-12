"""渲染质量评分定义：分类权重目录、校验与会话快照解析。"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

SCORING_CATEGORY_IDS: tuple[str, ...] = (
    "lighting",
    "material",
    "post_processing",
    "physics",
)

BUILTIN_CATEGORY_WEIGHTS: dict[str, float] = {
    "lighting": 25.0,
    "material": 25.0,
    "post_processing": 25.0,
    "physics": 25.0,
}

WEIGHT_SUM_TOLERANCE = 0.01

CATEGORY_CATALOG: list[dict[str, str]] = [
    {
        "id": "lighting",
        "label": "光照与阴影",
        "description": "实时光源、阴影与反射相关质量",
    },
    {
        "id": "material",
        "label": "材质与纹理",
        "description": "Draw Call、材质规模与纹理内存相关质量",
    },
    {
        "id": "post_processing",
        "label": "后处理与画面一致性",
        "description": "后处理 Volume、RenderTexture 与 GPU 帧预算压力",
    },
    {
        "id": "physics",
        "label": "物理仿真与虚实融合",
        "description": "刚体/碰撞体规模、穿模与 XR 姿态相关质量",
    },
]


class ScoringDefinitionValidationError(ValueError):
    """评分定义校验失败。"""


class ScoringDefinitionService:
    @classmethod
    def get_builtin_definition(cls) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "category_weights": dict(BUILTIN_CATEGORY_WEIGHTS),
        }

    @classmethod
    def get_catalog(cls) -> dict[str, Any]:
        return {"categories": [dict(item) for item in CATEGORY_CATALOG]}

    @classmethod
    def is_default(cls, definition: dict[str, Any]) -> bool:
        try:
            normalized = cls.validate_definition(definition)
        except ScoringDefinitionValidationError:
            return False
        builtin = cls.get_builtin_definition()
        for category_id in SCORING_CATEGORY_IDS:
            if normalized["category_weights"][category_id] != builtin["category_weights"][category_id]:
                return False
        return True

    @classmethod
    def compute_total_weight(cls, definition: dict[str, Any]) -> float:
        weights = definition.get("category_weights") or {}
        return round(sum(float(weights.get(key, 0)) for key in SCORING_CATEGORY_IDS), 4)

    @classmethod
    def validate_definition(cls, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ScoringDefinitionValidationError("评分定义必须是对象")

        schema_version = raw.get("schema_version", 1)
        if not isinstance(schema_version, int) or schema_version < 1:
            raise ScoringDefinitionValidationError("schema_version 无效")

        weights_raw = raw.get("category_weights")
        if not isinstance(weights_raw, dict):
            raise ScoringDefinitionValidationError("category_weights 必须是对象")

        unknown = sorted(set(weights_raw) - set(SCORING_CATEGORY_IDS))
        if unknown:
            raise ScoringDefinitionValidationError(f"包含未知分类：{', '.join(unknown)}")

        missing = [key for key in SCORING_CATEGORY_IDS if key not in weights_raw]
        if missing:
            raise ScoringDefinitionValidationError(f"缺少分类权重：{', '.join(missing)}")

        normalized_weights: dict[str, float] = {}
        for category_id in SCORING_CATEGORY_IDS:
            value = weights_raw[category_id]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ScoringDefinitionValidationError(f"{category_id} 权重必须是数字")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ScoringDefinitionValidationError(f"{category_id} 权重必须是有限数字")
            if numeric < 0 or numeric > 100:
                raise ScoringDefinitionValidationError(f"{category_id} 权重必须在 0 到 100 之间")
            normalized_weights[category_id] = round(numeric, 4)

        total = sum(normalized_weights.values())
        if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
            raise ScoringDefinitionValidationError(f"四项权重之和必须为 100%，当前为 {total:.2f}%")

        if all(weight <= 0 for weight in normalized_weights.values()):
            raise ScoringDefinitionValidationError("至少一项权重大于 0")

        return {
            "schema_version": schema_version,
            "category_weights": normalized_weights,
        }

    @classmethod
    def resolve_session_definition(cls, session_config: dict[str, Any] | None) -> dict[str, Any]:
        config = session_config or {}
        raw = config.get("scoring_definition")
        if raw is None:
            return {
                "definition": cls.get_builtin_definition(),
                "source": "builtin_default",
                "fallback_reason": None,
            }

        try:
            return {
                "definition": cls.validate_definition(raw),
                "source": "session_snapshot",
                "fallback_reason": None,
            }
        except ScoringDefinitionValidationError as exc:
            logger.warning("会话 scoring_definition 无效，回退内置默认：%s", exc)
            return {
                "definition": cls.get_builtin_definition(),
                "source": "builtin_default_fallback",
                "fallback_reason": str(exc),
            }

    @classmethod
    def build_response_summary(cls, definition: dict[str, Any]) -> dict[str, Any]:
        return {
            "total_weight": cls.compute_total_weight(definition),
            "is_default": cls.is_default(definition),
        }
