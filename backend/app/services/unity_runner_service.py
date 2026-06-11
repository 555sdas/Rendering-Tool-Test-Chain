import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.project import Project
from app.models.scene_asset import AssetType, SceneAsset
from app.models.test_session import TestSession, TestSessionStatus
from app.models.test_task import TestTask, TestTaskStatus


settings = get_settings()


class UnityRunnerService:
    def __init__(self, db: Session):
        self.db = db
        self.backend_root = Path(__file__).resolve().parents[2]
        self.resource_root = self._resolve_backend_path(settings.UNITY_RUNNER_RESOURCE_DIR)
        self.task_root = self._resolve_backend_path(settings.UNITY_RUNNER_TASK_DIR)
        self.log_root = self._resolve_backend_path(settings.UNITY_RUNNER_LOG_DIR)

    def list_engines(self) -> list[dict[str, Any]]:
        return [self._public_engine(item) for item in self._load_resource_items("unity_engines")]

    def list_scenes(self, project_id: int | None = None) -> list[dict[str, Any]]:
        scenes = self._load_resource_items("unity_projects")
        if project_id:
            scenes = [
                item for item in scenes
                if not item.get("platform_project_ids") or project_id in item.get("platform_project_ids", [])
            ]
        return [self._public_scene(item) for item in scenes]

    def start_test(
        self,
        *,
        project_id: int,
        unity_engine_id: str,
        scene_resource_id: str,
        quality_checks: dict[str, bool],
        quality_metric_checks: dict[str, bool],
        metric_checks: dict[str, bool],
        collect_interval: float,
        frame_rate_duration_seconds: float,
        metrics_duration_seconds: float,
        batchmode: bool,
        ensure_plugin: bool,
        creator_id: int,
    ) -> dict[str, Any]:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        engine = self._get_resource_item("unity_engines", unity_engine_id)
        scene = self._get_resource_item("unity_projects", scene_resource_id)
        self._validate_engine(engine)
        self._validate_scene(scene)

        if ensure_plugin:
            self._ensure_plugin_manifest(scene)

        scene_asset = self._ensure_scene_asset(project_id, scene)
        run_index = self._next_session_index(project_id)
        session_name = f"#{run_index}"

        config = self._build_session_config(
            project=project,
            engine=engine,
            scene=scene,
            quality_checks=quality_checks,
            quality_metric_checks=quality_metric_checks,
            metric_checks=metric_checks,
            collect_interval=collect_interval,
            frame_rate_duration_seconds=frame_rate_duration_seconds,
            metrics_duration_seconds=metrics_duration_seconds,
            run_index=run_index,
        )

        session = TestSession(
            name=session_name,
            description=f"由网页启动的 Unity 本地测试：{scene.get('name')}",
            status=TestSessionStatus.RUNNING.value,
            scene_id=scene_asset.id if scene_asset else None,
            user_id=creator_id,
            project_id=project_id,
            config=config,
            started_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.flush()

        task = TestTask(
            name=f"{project.name} - {scene.get('name')} - Unity 测试",
            description="网页创建并由后端启动 Unity 的本地测试任务",
            status=TestTaskStatus.RUNNING.value,
            task_type="unity_local_render_test",
            priority=0,
            project_id=project_id,
            scene_id=session.scene_id,
            creator_id=creator_id,
            config=config,
            started_at=datetime.utcnow(),
        )
        self.db.add(task)
        self.db.flush()

        task_config_path, unity_log_path, runner_log_path = self._write_task_config(
            task=task,
            session=session,
            engine=engine,
            scene=scene,
            quality_checks=quality_checks,
            quality_metric_checks=quality_metric_checks,
            metric_checks=metric_checks,
            collect_interval=collect_interval,
            frame_rate_duration_seconds=frame_rate_duration_seconds,
            metrics_duration_seconds=metrics_duration_seconds,
            batchmode=batchmode,
        )
        self._append_runner_log(
            runner_log_path,
            "INFO",
            f"启动 Unity 测试任务：task={task.id}, session={session.id}, project={project.name}",
        )
        self._append_runner_log(
            runner_log_path,
            "INFO",
            f"引擎：{engine.get('name')} ({engine.get('executable_path')})",
        )
        self._append_runner_log(
            runner_log_path,
            "INFO",
            f"场景：{scene.get('name')} ({scene.get('scene_path')})",
        )
        self._append_runner_log(
            runner_log_path,
            "INFO",
            "采集配置：间隔 %.2fs，帧率阶段 %.1fs，指标阶段 %.1fs，性能项=%s，质量项=%s"
            % (
                collect_interval,
                frame_rate_duration_seconds,
                metrics_duration_seconds,
                self._enabled_names(metric_checks, self._metric_check_labels()),
                self._enabled_names(quality_checks, self._quality_check_labels()),
            ),
        )

        try:
            process = self._launch_unity(
                engine=engine,
                scene=scene,
                task_config_path=task_config_path,
                log_path=unity_log_path,
                batchmode=batchmode,
            )
        except Exception as exc:
            task.status = TestTaskStatus.FAILED.value
            task.error_message = str(exc)
            task.completed_at = datetime.utcnow()
            session.status = TestSessionStatus.FAILED.value
            session.ended_at = datetime.utcnow()
            if session.started_at:
                session.duration_seconds = (session.ended_at - session.started_at).total_seconds()
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"启动 Unity 失败：{exc}") from exc

        task_config = dict(task.config or {})
        task_config.update(
            {
                "process_id": process.pid,
                "task_config_path": str(task_config_path),
                "unity_log_path": str(unity_log_path),
                "runner_log_path": str(runner_log_path),
                "platform_session_id": session.id,
            }
        )
        task.config = task_config

        session_config = dict(session.config or {})
        session_config.update(
            {
                "test_task_id": task.id,
                "process_id": process.pid,
                "task_config_path": str(task_config_path),
                "unity_log_path": str(unity_log_path),
                "runner_log_path": str(runner_log_path),
            }
        )
        session.config = session_config

        self.db.commit()
        self.db.refresh(task)
        self.db.refresh(session)

        self._append_runner_log(runner_log_path, "INFO", f"Unity 进程已启动：pid={process.pid}")

        return {
            "task": self._task_response(task),
            "session": self._session_response(session),
            "engine": self._public_engine(engine),
            "scene": self._public_scene(scene),
            "process_id": process.pid,
            "task_config_path": str(task_config_path),
            "unity_log_path": str(unity_log_path),
            "runner_log_path": str(runner_log_path),
        }

    def stop_test(self, task_id: int) -> dict[str, Any]:
        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unity 测试任务不存在")

        task_config = dict(task.config or {})
        runner_log_path = self._path_or_none(task_config.get("runner_log_path"))
        pid = self._int_or_none(task_config.get("process_id"))

        if self._task_status_value(task.status) not in {
            TestTaskStatus.COMPLETED.value,
            TestTaskStatus.FAILED.value,
            TestTaskStatus.CANCELLED.value,
        }:
            self._append_runner_log(runner_log_path, "WARN", f"收到停止请求，准备终止 Unity 进程：pid={pid or '-'}")
            if pid:
                self._terminate_process(pid, runner_log_path)
            task.status = TestTaskStatus.CANCELLED.value
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
            task.error_message = "用户从 Web 端停止 Unity 测试"

        session = self._find_task_session(task)
        if session and self._session_status_value(session.status) not in {
            TestSessionStatus.COMPLETED.value,
            TestSessionStatus.FAILED.value,
            TestSessionStatus.CANCELLED.value,
        }:
            session.status = TestSessionStatus.CANCELLED.value
            session.ended_at = datetime.utcnow()
            if session.started_at:
                session.duration_seconds = (session.ended_at - session.started_at).total_seconds()

        self.db.commit()
        self.db.refresh(task)
        if session:
            self.db.refresh(session)
        self._append_runner_log(runner_log_path, "INFO", "Unity 停止流程已完成，会话已标记为已取消。")

        return {
            "task": self._task_response(task),
            "session": self._session_response(session) if session else None,
        }

    def get_task_logs(self, task_id: int, tail_lines: int = 220) -> dict[str, Any]:
        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unity 测试任务不存在")

        session = self._find_task_session(task)
        self._sync_completed_task_from_session(task, session)

        config = dict(task.config or {})
        runner_log_path = self._path_or_none(config.get("runner_log_path"))
        unity_log_path = self._path_or_none(config.get("unity_log_path"))

        runner_lines = self._tail_lines(runner_log_path, max(20, tail_lines // 3), "Runner 日志尚未生成。")
        unity_lines = self._tail_lines(unity_log_path, tail_lines, "Unity 日志尚未生成，等待编辑器启动。")
        lines = runner_lines + unity_lines
        if len(lines) > tail_lines:
            lines = lines[-tail_lines:]

        return {
            "task": self._task_response(task),
            "session": self._session_response(session) if session else None,
            "runner_log_path": str(runner_log_path) if runner_log_path else None,
            "unity_log_path": str(unity_log_path) if unity_log_path else None,
            "lines": lines,
        }

    def _resolve_backend_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.backend_root / path
        return path

    def _load_resource_items(self, kind: str) -> list[dict[str, Any]]:
        root = self.resource_root / kind
        if not root.exists():
            return []

        items: list[dict[str, Any]] = []
        for path in sorted(root.glob("*.json")):
            with path.open("r", encoding="utf-8") as file:
                item = json.load(file)
            item.setdefault("id", path.stem)
            item["_config_path"] = str(path)
            items.append(item)
        return items

    def _get_resource_item(self, kind: str, item_id: str) -> dict[str, Any]:
        for item in self._load_resource_items(kind):
            if item.get("id") == item_id:
                return item
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"资源配置不存在：{item_id}")

    def _validate_engine(self, engine: dict[str, Any]) -> None:
        executable_path = Path(engine.get("executable_path", ""))
        if not executable_path.exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unity 引擎路径不存在：{executable_path}")

    def _validate_scene(self, scene: dict[str, Any]) -> None:
        project_path = Path(scene.get("project_path", ""))
        if not project_path.exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unity 项目路径不存在：{project_path}")

        scene_file = project_path / scene.get("scene_path", "")
        if not scene_file.exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unity 场景文件不存在：{scene_file}")

    def _ensure_plugin_manifest(self, scene: dict[str, Any]) -> None:
        project_path = Path(scene.get("project_path", ""))
        manifest_path = project_path / "Packages" / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unity manifest 不存在：{manifest_path}")

        package_name = scene.get("collector_package_name") or "com.xr.testdatacollector"
        package_path = Path(scene.get("collector_package_path") or self.backend_root.parent / "unity-xr-collector")
        dependency_value = "file:" + package_path.as_posix()

        with manifest_path.open("r", encoding="utf-8-sig") as file:
            manifest = json.load(file)
        dependencies = manifest.setdefault("dependencies", {})
        if dependencies.get(package_name) == dependency_value:
            return
        if package_name in dependencies:
            return

        dependencies[package_name] = dependency_value
        with manifest_path.open("w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def _ensure_scene_asset(self, project_id: int, scene: dict[str, Any]) -> SceneAsset:
        project_path = Path(scene.get("project_path", ""))
        scene_file = project_path / scene.get("scene_path", "")
        file_path = str(scene_file)

        asset = (
            self.db.query(SceneAsset)
            .filter(SceneAsset.project_id == project_id)
            .filter(SceneAsset.file_path == file_path)
            .first()
        )
        if asset:
            return asset

        file_size = scene_file.stat().st_size if scene_file.exists() else 0
        asset = SceneAsset(
            name=scene.get("name") or scene_file.stem,
            description=scene.get("description"),
            asset_type=AssetType.SCENE.value,
            file_path=file_path,
            file_size=file_size,
            version=scene.get("version"),
            tags=scene.get("tags") or [],
            asset_metadata={
                "unity_project_path": str(project_path),
                "unity_scene_path": scene.get("scene_path"),
                "collector_package_name": scene.get("collector_package_name"),
                "collector_package_path": scene.get("collector_package_path"),
            },
            is_public=False,
            project_id=project_id,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def _next_session_index(self, project_id: int) -> int:
        session_count = (
            self.db.query(func.count(TestSession.id))
            .filter(TestSession.project_id == project_id)
            .scalar()
            or 0
        )
        return session_count + 1

    def _build_session_config(
        self,
        *,
        project: Project,
        engine: dict[str, Any],
        scene: dict[str, Any],
        quality_checks: dict[str, bool],
        quality_metric_checks: dict[str, bool],
        metric_checks: dict[str, bool],
        collect_interval: float,
        frame_rate_duration_seconds: float,
        metrics_duration_seconds: float,
        run_index: int,
    ) -> dict[str, Any]:
        return {
            "source": "web_unity_runner",
            "platform_project_id": project.id,
            "platform_project_name": project.name,
            "run_index": run_index,
            "session_sequence": run_index,
            "unity_engine_id": engine.get("id"),
            "unity_engine_name": engine.get("name"),
            "unity_version": engine.get("version"),
            "unity_executable_path": engine.get("executable_path"),
            "scene_resource_id": scene.get("id"),
            "scene_resource_name": scene.get("name"),
            "unity_project_path": scene.get("project_path"),
            "unity_scene_path": scene.get("scene_path"),
            "collector_package_name": scene.get("collector_package_name"),
            "collector_package_path": scene.get("collector_package_path"),
            "quality_checks": quality_checks,
            "quality_metric_checks": quality_metric_checks,
            "metric_checks": metric_checks,
            "collect_interval": collect_interval,
            "frame_rate_duration_seconds": frame_rate_duration_seconds,
            "metrics_duration_seconds": metrics_duration_seconds,
        }

    def _write_task_config(
        self,
        *,
        task: TestTask,
        session: TestSession,
        engine: dict[str, Any],
        scene: dict[str, Any],
        quality_checks: dict[str, bool],
        quality_metric_checks: dict[str, bool],
        metric_checks: dict[str, bool],
        collect_interval: float,
        frame_rate_duration_seconds: float,
        metrics_duration_seconds: float,
        batchmode: bool,
    ) -> tuple[Path, Path, Path]:
        self.task_root.mkdir(parents=True, exist_ok=True)
        self.log_root.mkdir(parents=True, exist_ok=True)

        task_config_path = self.task_root / f"unity_task_{task.id}_session_{session.id}.json"
        unity_log_path = self.log_root / f"unity_task_{task.id}_session_{session.id}.unity.log"
        runner_log_path = self.log_root / f"unity_task_{task.id}_session_{session.id}.runner.log"
        upload_url = f"{settings.UNITY_RUNNER_PLATFORM_BASE_URL.rstrip('/')}/data-collection/test-sessions/{session.id}/samples/batch"

        payload = {
            "taskId": task.id,
            "platformSessionId": session.id,
            "sessionName": session.name,
            "projectId": session.project_id,
            "sceneId": session.scene_id or 0,
            "projectName": (session.config or {}).get("platform_project_name", ""),
            "platformBaseUrl": settings.UNITY_RUNNER_PLATFORM_BASE_URL,
            "uploadUrl": upload_url,
            "deviceToken": settings.DEVICE_TOKEN,
            "unityEnginePath": engine.get("executable_path"),
            "unityProjectPath": scene.get("project_path"),
            "unityScenePath": scene.get("scene_path"),
            "collectInterval": collect_interval,
            "frameRateDurationSeconds": frame_rate_duration_seconds,
            "metricsDurationSeconds": metrics_duration_seconds,
            "collectFrameRate": metric_checks.get("frame_rate", True),
            "collectFrameTime": metric_checks.get("frame_time", True),
            "collectCpuUsage": metric_checks.get("cpu", True),
            "collectGpuUsage": metric_checks.get("gpu", True),
            "collectMemory": metric_checks.get("memory", True),
            "collectDeviceInfo": metric_checks.get("device_info", True),
            "enableNetworkUpload": True,
            "autoCreateSession": False,
            "autoStart": True,
            "quitOnComplete": True,
            "batchmode": batchmode,
            "qualityChecks": {
                "lighting": quality_checks.get("lighting", True),
                "materials": quality_checks.get("materials", True),
                "postProcessing": quality_checks.get("post_processing", True),
                "physics": quality_checks.get("physics", True),
            },
            "qualityMetricChecks": self._quality_metric_payload(quality_metric_checks),
        }
        with task_config_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        return task_config_path, unity_log_path, runner_log_path

    def _launch_unity(
        self,
        *,
        engine: dict[str, Any],
        scene: dict[str, Any],
        task_config_path: Path,
        log_path: Path,
        batchmode: bool,
    ) -> subprocess.Popen:
        command = [
            engine["executable_path"],
            "-projectPath",
            scene["project_path"],
            "-executeMethod",
            "XRDataCollector.Editor.XRBatchTestRunner.RunFromCommandLine",
            "-xrTaskConfig",
            str(task_config_path),
            "-logFile",
            str(log_path),
        ]
        if batchmode:
            command.insert(1, "-batchmode")

        return subprocess.Popen(command, cwd=str(self.backend_root))

    def _find_task_session(self, task: TestTask) -> TestSession | None:
        config = dict(task.config or {})
        session_id = self._int_or_none(config.get("platform_session_id"))
        if session_id:
            return self.db.query(TestSession).filter(TestSession.id == session_id).first()
        return (
            self.db.query(TestSession)
            .filter(TestSession.project_id == task.project_id)
            .filter(TestSession.config["test_task_id"].as_integer() == task.id)
            .first()
        )

    def _sync_completed_task_from_session(self, task: TestTask, session: TestSession | None) -> None:
        if not session:
            return
        session_status = self._session_status_value(session.status)
        task_status = self._task_status_value(task.status)
        if task_status not in {TestTaskStatus.RUNNING.value, TestTaskStatus.QUEUED.value, TestTaskStatus.PENDING.value}:
            return
        if session_status == TestSessionStatus.COMPLETED.value:
            task.status = TestTaskStatus.COMPLETED.value
        elif session_status == TestSessionStatus.FAILED.value:
            task.status = TestTaskStatus.FAILED.value
        elif session_status == TestSessionStatus.CANCELLED.value:
            task.status = TestTaskStatus.CANCELLED.value
        else:
            return
        task.completed_at = task.completed_at or session.ended_at or datetime.utcnow()
        if task.started_at and task.completed_at:
            task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
        self.db.commit()
        self.db.refresh(task)

    def _terminate_process(self, pid: int, runner_log_path: Path | None) -> None:
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    self._append_runner_log(runner_log_path, "INFO", f"Unity 进程已终止：pid={pid}")
                else:
                    detail = (result.stderr or result.stdout or "").strip()
                    self._append_runner_log(runner_log_path, "WARN", f"终止进程返回非零状态：pid={pid}，{detail}")
            else:
                os.kill(pid, 15)
                self._append_runner_log(runner_log_path, "INFO", f"Unity 进程已发送终止信号：pid={pid}")
        except Exception as exc:
            self._append_runner_log(runner_log_path, "WARN", f"终止 Unity 进程失败：pid={pid}，{exc}")

    def _tail_lines(self, path: Path | None, limit: int, missing_message: str) -> list[str]:
        if not path or not path.exists():
            return [missing_message]
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            lines = path.read_text(errors="replace").splitlines()
        return lines[-limit:] if lines else ["日志文件为空，等待新的输出。"]

    def _append_runner_log(self, path: Path | None, level: str, message: str) -> None:
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp} UTC] [{level}] {message}\n")

    def _enabled_names(self, values: dict[str, bool], labels: dict[str, str] | None = None) -> str:
        labels = labels or {}
        enabled = [labels.get(key, key) for key, value in values.items() if value]
        return ", ".join(enabled) if enabled else "未选择"

    def _metric_check_labels(self) -> dict[str, str]:
        return {
            "frame_rate": "FPS",
            "frame_time": "帧时间",
            "cpu": "CPU",
            "gpu": "GPU/渲染统计",
            "memory": "内存",
            "device_info": "设备信息",
        }

    def _quality_check_labels(self) -> dict[str, str]:
        return {
            "lighting": "光照与阴影",
            "materials": "材质与纹理",
            "post_processing": "后处理",
            "physics": "物理仿真",
        }

    def _quality_metric_payload(self, checks: dict[str, bool]) -> dict[str, bool]:
        def enabled(key: str) -> bool:
            return bool(checks.get(key, True))

        return {
            "lightingActiveLights": enabled("lighting.active_lights"),
            "lightingRealtimeLights": enabled("lighting.realtime_lights"),
            "lightingShadowCasters": enabled("lighting.shadow_casters"),
            "lightingReflectionProbes": enabled("lighting.reflection_probes"),
            "lightingExposureArtifacts": enabled("lighting.exposure_artifacts"),
            "materialSlots": enabled("materials.material_slots"),
            "materialUniqueMaterials": enabled("materials.unique_materials"),
            "materialTransparentMaterials": enabled("materials.transparent_materials"),
            "materialDrawCalls": enabled("materials.draw_calls"),
            "materialTextureMemory": enabled("materials.texture_memory"),
            "postProcessVolumes": enabled("post_processing.volumes"),
            "postProcessRenderTextures": enabled("post_processing.render_textures"),
            "postProcessRenderTextureMemory": enabled("post_processing.render_texture_memory"),
            "postProcessGpuFrameBudget": enabled("post_processing.gpu_frame_budget"),
            "postProcessWarnings": enabled("post_processing.warnings"),
            "physicsRigidbodies": enabled("physics.rigidbodies"),
            "physicsColliders": enabled("physics.colliders"),
            "physicsPenetration": enabled("physics.penetration"),
            "physicsPoseLatency": enabled("physics.pose_latency"),
            "physicsPredictionError": enabled("physics.prediction_error"),
            "physicsLongFrames": enabled("physics.long_frames"),
        }

    def _path_or_none(self, value: Any) -> Path | None:
        if isinstance(value, str) and value.strip():
            return Path(value)
        return None

    def _int_or_none(self, value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _task_status_value(self, value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    def _session_status_value(self, value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    def _public_engine(self, item: dict[str, Any]) -> dict[str, Any]:
        executable_path = item.get("executable_path")
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "version": item.get("version"),
            "executable_path": executable_path,
            "enabled": item.get("enabled", True),
            "is_default": item.get("is_default", False),
            "exists": Path(executable_path or "").exists(),
            "notes": item.get("notes"),
        }

    def _public_scene(self, item: dict[str, Any]) -> dict[str, Any]:
        project_path = Path(item.get("project_path", ""))
        scene_file = project_path / item.get("scene_path", "")
        manifest = project_path / "Packages" / "manifest.json"
        package_name = item.get("collector_package_name") or "com.xr.testdatacollector"
        manifest_has_plugin = False
        if manifest.exists():
            try:
                with manifest.open("r", encoding="utf-8-sig") as file:
                    dependencies = json.load(file).get("dependencies", {})
                manifest_has_plugin = package_name in dependencies
            except Exception:
                manifest_has_plugin = False

        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "project_path": item.get("project_path"),
            "scene_path": item.get("scene_path"),
            "scene_file_path": str(scene_file),
            "enabled": item.get("enabled", True),
            "exists": scene_file.exists(),
            "collector_package_name": package_name,
            "collector_package_path": item.get("collector_package_path"),
            "manifest_has_plugin": manifest_has_plugin,
            "tags": item.get("tags") or [],
        }

    def _task_response(self, task: TestTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "status": task.status.value if hasattr(task.status, "value") else task.status,
            "task_type": task.task_type,
            "project_id": task.project_id,
            "scene_id": task.scene_id,
            "config": task.config,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "duration_seconds": task.duration_seconds,
            "error_message": task.error_message,
        }

    def _session_response(self, session: TestSession) -> dict[str, Any]:
        return {
            "id": session.id,
            "name": session.name,
            "description": session.description,
            "status": session.status.value if hasattr(session.status, "value") else session.status,
            "device_model": session.device_model,
            "os_version": session.os_version,
            "xr_runtime": session.xr_runtime,
            "app_version": session.app_version,
            "scene_id": session.scene_id,
            "user_id": session.user_id,
            "project_id": session.project_id,
            "config": session.config,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "duration_seconds": session.duration_seconds,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
