"""测试会话展示字段辅助。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def get_session_scene_display_name(
    *,
    config: dict[str, Any] | None,
    scene_id: int | None = None,
    scene_asset_name: str | None = None,
) -> str | None:
    """从会话 config 或场景资产解析用于 UI 展示的场景名。"""
    data = config or {}
    for key in ("scene_resource_name", "scene_name", "sceneName", "unity_scene_name"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()

    if scene_asset_name and str(scene_asset_name).strip():
        return str(scene_asset_name).strip()

    path_value = data.get("unity_scene_path") or data.get("unityScenePath")
    if path_value is not None and str(path_value).strip():
        stem = Path(str(path_value).replace("\\", "/")).stem
        if stem:
            return stem

    if scene_id:
        return f"场景 #{scene_id}"
    return None
