import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.config import get_settings


settings = get_settings()


class SystemSettingsService:
    def __init__(self):
        self.backend_root = Path(__file__).resolve().parents[2]
        self.settings_path = self._resolve_backend_path(settings.SYSTEM_SETTINGS_PATH)

    def get_unity_settings(self) -> dict[str, Any]:
        data = self._load()
        unity = data.get("unity") if isinstance(data.get("unity"), dict) else {}
        result = {
            "unity_executable_path": str(unity.get("unity_executable_path") or ""),
            "unity_project_path": str(unity.get("unity_project_path") or ""),
            "unity_scene_path": str(unity.get("unity_scene_path") or ""),
            "collector_package_path": str(unity.get("collector_package_path") or ""),
        }
        return {
            **result,
            "status": self._build_status(result),
            "settings_file": str(self.settings_path),
        }

    def update_unity_settings(self, values: dict[str, str]) -> dict[str, Any]:
        data = self._load()
        data["unity"] = {
            "unity_executable_path": values.get("unity_executable_path", "").strip(),
            "unity_project_path": values.get("unity_project_path", "").strip(),
            "unity_scene_path": values.get("unity_scene_path", "").strip(),
            "collector_package_path": values.get("collector_package_path", "").strip(),
        }
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        with self.settings_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return self.get_unity_settings()

    def get_unity_resources(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        config = self.get_unity_settings()
        executable_path = config["unity_executable_path"]
        engine = None
        if executable_path:
            engine = {
                "id": "system-settings-engine",
                "name": "系统设置中的 Unity",
                "version": "",
                "executable_path": executable_path,
                "enabled": True,
                "is_default": True,
                "notes": "由系统设置页面维护",
            }

        scenes = self.get_unity_scene_resources()
        scene = scenes[0] if scenes else None
        return engine, scene

    def discover_unity_scenes(self, project_path: str) -> list[str]:
        root = Path(project_path)
        assets_dir = root / "Assets"
        if not assets_dir.is_dir():
            return []

        discovered: list[str] = []
        for scene_file in sorted(assets_dir.rglob("*.unity")):
            if not scene_file.is_file():
                continue
            discovered.append(scene_file.relative_to(root).as_posix())
        return discovered

    def get_unity_scene_resources(self) -> list[dict[str, Any]]:
        config = self.get_unity_settings()
        project_path = config["unity_project_path"]
        if not project_path:
            return []

        package_path = config["collector_package_path"] or None
        relative_paths = self.discover_unity_scenes(project_path)

        legacy_scene_path = config["unity_scene_path"].strip()
        if legacy_scene_path and legacy_scene_path not in relative_paths:
            relative_paths.insert(0, legacy_scene_path)

        default_scene_path = config["unity_scene_path"].strip()
        resources: list[dict[str, Any]] = []
        for index, scene_path in enumerate(relative_paths):
            is_default = scene_path == default_scene_path if default_scene_path else index == 0
            resources.append({
                "id": self._scene_resource_id(scene_path),
                "name": Path(scene_path).stem or "未命名场景",
                "description": scene_path,
                "project_path": project_path,
                "scene_path": scene_path,
                "collector_package_name": "com.xr.testdatacollector",
                "collector_package_path": package_path,
                "enabled": True,
                "is_default": is_default,
                "tags": ["系统设置", "自动发现"],
            })
        return resources

    def _scene_resource_id(self, scene_path: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", scene_path.replace(".unity", "")).strip("-").lower()
        if not slug or len(slug) > 48:
            digest = hashlib.md5(scene_path.encode("utf-8")).hexdigest()[:12]
            return f"system-settings-scene-{digest}"
        return f"system-settings-scene-{slug}"

    def _build_status(self, values: dict[str, str]) -> dict[str, bool | int | list[str]]:
        executable = Path(values["unity_executable_path"]) if values["unity_executable_path"] else None
        project = Path(values["unity_project_path"]) if values["unity_project_path"] else None
        package = Path(values["collector_package_path"]) if values["collector_package_path"] else None
        discovered_scenes = self.discover_unity_scenes(values["unity_project_path"]) if project and project.is_dir() else []
        legacy_scene = project / values["unity_scene_path"] if project and values["unity_scene_path"] else None
        return {
            "unity_executable_exists": bool(executable and executable.is_file()),
            "unity_project_exists": bool(project and project.is_dir()),
            "unity_scene_exists": bool(discovered_scenes) or bool(legacy_scene and legacy_scene.is_file()),
            "discovered_scene_count": len(discovered_scenes),
            "discovered_scenes": discovered_scenes[:20],
            "collector_package_exists": bool(package and package.is_dir()),
        }

    def _load(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            with self.settings_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _resolve_backend_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.backend_root / path
        return path
