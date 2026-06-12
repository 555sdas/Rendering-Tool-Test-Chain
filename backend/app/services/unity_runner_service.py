import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.project import Project
from app.models.scene_asset import AssetType, SceneAsset
from app.models.test_session import TestSession, TestSessionStatus
from app.models.test_task import TestTask, TestTaskStatus
from app.services.system_settings_service import SystemSettingsService
from app.services.test_scope_service import TestScopeService
from app.utils.datetime import to_utc_naive


settings = get_settings()


class UnityRunnerService:
    UNITY_PROCESS_POLL_SECONDS = 1.0
    UNITY_COMPLETED_EXIT_GRACE_SECONDS = 20.0
    UNITY_TERMINATE_GRACE_SECONDS = 8.0
    UNITY_FORCE_KILL_WAIT_SECONDS = 5.0

    PLUGIN_LOG_MARKERS = (
        "XRBatchTestRunner",
        "XRTestManager",
        "TestSceneFlythroughActivator",
        "UnityProgressReporter",
        "TestDataUploader",
        "XRDataCollector",
        "[PROGRESS]",
        "采集进度",
        "采集配置",
        "启动 Unity",
        "Unity 进程",
        "任务已投递",
        "上传",
        "样本 #",
        "阶段1",
        "阶段2",
        "Play Mode",
        "自动巡航",
    )

    UNITY_FATAL_LOG_MARKERS = {
        "executeMethod class": "Unity 找不到自动化入口，请确认采集插件已成功编译。",
        "Scripts have compiler errors": "Unity 项目存在脚本编译错误。",
        "Compilation failed": "Unity 项目脚本编译失败。",
        "Aborting batchmode due to failure": "Unity BatchMode 执行失败。",
        "String conversion error: Illegal byte sequence": "Unity 读取启动环境变量失败。",
    }

    UNITY_LOG_NOISE_MARKERS = (
        "[Licensing::Client]",
    )

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

    def get_test_metrics_catalog(self) -> dict[str, Any]:
        return TestScopeService.get_catalog()

    def get_default_test_scope_for_run(self) -> dict[str, Any]:
        return SystemSettingsService().get_default_test_scope()["default_scope"]

    def resolve_scope_bundle(
        self,
        *,
        test_scope: dict[str, Any] | None,
        metric_checks: dict[str, bool],
        quality_checks: dict[str, bool],
        quality_metric_checks: dict[str, bool],
    ) -> dict[str, Any]:
        if test_scope:
            scope = TestScopeService.normalize_scope(test_scope, source="single_run_override")
        else:
            legacy = {
                "metric_checks": metric_checks,
                "quality_checks": quality_checks,
                "quality_metric_checks": quality_metric_checks,
            }
            has_legacy_override = (
                any(not value for value in metric_checks.values())
                or any(not value for value in quality_checks.values())
                or bool(quality_metric_checks)
            )
            if has_legacy_override:
                scope = TestScopeService.normalize_scope(None, legacy_fields=legacy, source="single_run_override")
            else:
                scope = TestScopeService.normalize_scope(
                    self.get_default_test_scope_for_run(),
                    source="global_default",
                )
        TestScopeService.validate_scope(scope)
        legacy_fields = TestScopeService.to_legacy_fields(scope)
        execution_plan = TestScopeService.resolve_execution_plan(scope)
        return {
            "test_scope": scope,
            "metric_checks": legacy_fields["metric_checks"],
            "quality_checks": legacy_fields["quality_checks"],
            "quality_metric_checks": legacy_fields["quality_metric_checks"],
            "execution_plan": execution_plan,
            "test_scope_summary": TestScopeService.build_scope_summary(scope),
        }

    def start_test(
        self,
        *,
        project_id: int,
        unity_engine_id: str,
        scene_resource_id: str,
        test_scope: dict[str, Any] | None = None,
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

        scope_bundle = self.resolve_scope_bundle(
            test_scope=test_scope,
            metric_checks=metric_checks,
            quality_checks=quality_checks,
            quality_metric_checks=quality_metric_checks,
        )
        metric_checks = scope_bundle["metric_checks"]
        quality_checks = scope_bundle["quality_checks"]
        quality_metric_checks = scope_bundle["quality_metric_checks"]

        from app.services.system_settings_service import SystemSettingsService

        config = SystemSettingsService().attach_scoring_definition_snapshot(
            self._build_session_config(
                project=project,
                engine=engine,
                scene=scene,
                scope_bundle=scope_bundle,
                collect_interval=collect_interval,
                frame_rate_duration_seconds=frame_rate_duration_seconds,
                metrics_duration_seconds=metrics_duration_seconds,
                run_index=run_index,
            )
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
            scope_bundle=scope_bundle,
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
            "采集配置：间隔 %.2fs，帧率阶段 %.1fs，指标阶段 %.1fs，测试范围=%s，跳过=%s"
            % (
                collect_interval,
                frame_rate_duration_seconds,
                metrics_duration_seconds,
                "、".join(scope_bundle["test_scope_summary"]["selected_labels"][:8]),
                scope_bundle["test_scope_summary"]["skipped_count"],
            ),
        )

        try:
            process = self._launch_unity(
                engine=engine,
                scene=scene,
                task_config_path=task_config_path,
                log_path=unity_log_path,
                runner_log_path=runner_log_path,
                batchmode=batchmode,
            )
        except Exception as exc:
            task.status = TestTaskStatus.FAILED.value
            task.error_message = str(exc)
            task.completed_at = datetime.utcnow()
            session.status = TestSessionStatus.FAILED.value
            session.ended_at = datetime.utcnow()
            if session.started_at:
                session.duration_seconds = self._duration_seconds(session.started_at, session.ended_at)
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"启动 Unity 失败：{exc}") from exc

        task_config = dict(task.config or {})
        task_config.update(
            {
                "process_id": process.pid if process else None,
                "launch_mode": "new_editor" if process else "existing_editor",
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
                "process_id": process.pid if process else None,
                "launch_mode": "new_editor" if process else "existing_editor",
                "task_config_path": str(task_config_path),
                "unity_log_path": str(unity_log_path),
                "runner_log_path": str(runner_log_path),
            }
        )
        session.config = session_config

        self.db.commit()
        self.db.refresh(task)
        self.db.refresh(session)

        if process:
            self._append_runner_log(runner_log_path, "INFO", f"Unity 进程已启动：pid={process.pid}")
            self._monitor_unity_process(
                process=process,
                task_id=task.id,
                session_id=session.id,
                runner_log_path=runner_log_path,
            )
        else:
            self._append_runner_log(runner_log_path, "INFO", "任务已投递到当前打开的 Unity Editor。")

        return {
            "task": self._task_response(task),
            "session": self._session_response(session),
            "engine": self._public_engine(engine),
            "scene": self._public_scene(scene),
            "process_id": process.pid if process else None,
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
            task.status = TestTaskStatus.CANCELLED.value
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration_seconds = self._duration_seconds(task.started_at, task.completed_at)
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
                session.duration_seconds = self._duration_seconds(session.started_at, session.ended_at)

        self.db.commit()
        self.db.refresh(task)
        if session:
            self.db.refresh(session)
        if pid:
            self._terminate_process(pid, runner_log_path)
        else:
            self._request_existing_editor_stop(task_config, task.id, runner_log_path)
        self._append_runner_log(runner_log_path, "INFO", "Unity 停止流程已完成，会话已标记为已取消。")

        return {
            "task": self._task_response(task),
            "session": self._session_response(session) if session else None,
        }

    def get_task_logs(self, task_id: int, tail_lines: int = 400) -> dict[str, Any]:
        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unity 测试任务不存在")

        session = self._find_task_session(task)
        self._sync_completed_task_from_session(task, session)
        self._sync_stale_task(task, session)

        config = dict(task.config or {})
        runner_log_path = self._path_or_none(config.get("runner_log_path"))
        unity_log_path = self._path_or_none(config.get("unity_log_path"))

        runner_limit = max(40, int(tail_lines * 0.45))
        unity_limit = max(60, tail_lines - runner_limit)
        runner_raw = self._read_log_lines(runner_log_path)
        unity_raw = self._read_log_lines(unity_log_path)

        lines: list[str] = []
        if runner_raw:
            lines.append("──────── 后端 Runner / 采集进度 ────────")
            lines.extend(runner_raw[-runner_limit:])
        else:
            lines.append("Runner 日志尚未生成。")

        launch_mode = config.get("launch_mode") or "new_editor"
        unity_filtered = self._filter_unity_log_lines(unity_raw, unity_limit)
        unity_section_title = "──────── Unity 插件 / 关键事件 ────────"
        if unity_filtered:
            lines.append(unity_section_title)
            lines.extend(unity_filtered)
        elif unity_raw:
            lines.append("──────── Unity 原始日志（末尾） ────────")
            lines.extend(unity_raw[-min(30, unity_limit):])
        else:
            editor_scoped = self._read_editor_log_for_task(
                task_id=task.id,
                session_id=session.id if session else None,
            )
            editor_filtered = self._filter_unity_log_lines(editor_scoped, unity_limit)
            if editor_filtered:
                lines.append("──────── Unity 插件 / 关键事件（Editor.log）────────")
                lines.extend(editor_filtered)
            else:
                lines.extend(self._missing_unity_log_lines(launch_mode))

        if len(lines) > tail_lines:
            lines = lines[-tail_lines:]
        self._sync_failed_task_from_logs(task, session, lines, runner_log_path)

        return {
            "task": self._task_response(task),
            "session": self._session_response(session) if session else None,
            "runner_log_path": str(runner_log_path) if runner_log_path else None,
            "unity_log_path": str(unity_log_path) if unity_log_path else None,
            "lines": lines,
        }

    def append_progress_event_log(self, task: TestTask, payload: dict[str, Any]) -> None:
        config = dict(task.config or {})
        runner_log_path = self._path_or_none(config.get("runner_log_path"))
        if not runner_log_path:
            return

        summary = dict(task.result_summary or {})
        last_logged_at = summary.get("progress_log_last_at")
        last_phase = summary.get("progress_log_last_phase")
        last_sample_bucket = summary.get("progress_log_last_sample_bucket")
        now = datetime.utcnow()

        phase = str(payload.get("phase_label") or payload.get("phase") or "-")
        sample_count = int(payload.get("sample_count") or 0)
        sample_bucket = sample_count // 5
        elapsed_seconds = 0.0
        if isinstance(last_logged_at, str) and last_logged_at:
            try:
                elapsed_seconds = (now - datetime.fromisoformat(last_logged_at.replace("Z", ""))).total_seconds()
            except ValueError:
                elapsed_seconds = 999.0

        should_log = (
            phase != last_phase
            or sample_bucket != last_sample_bucket
            or not last_logged_at
            or elapsed_seconds >= 6
        )
        if not should_log:
            return

        progress_pct = float(payload.get("progress") or 0) * 100
        message = (
            f"进度 {progress_pct:.0f}% | 阶段={phase} | 样本={sample_count} | "
            f"FPS={float(payload.get('fps') or 0):.1f} | "
            f"帧时={float(payload.get('frame_time_ms') or 0):.2f}ms | "
            f"CPU={float(payload.get('cpu_usage_percent') or 0):.1f}% | "
            f"GPU={float(payload.get('gpu_usage_percent') or 0):.1f}% | "
            f"内存={float(payload.get('memory_mb') or 0):.0f}MB | "
            f"显存={float(payload.get('graphics_memory_mb') or 0):.0f}MB | "
            f"DrawCalls={int(payload.get('draw_calls') or 0)} | "
            f"三角面={int(payload.get('triangles') or 0)} | "
            f"顶点={int(payload.get('vertices') or 0)} | "
            f"光源={int(payload.get('active_light_count') or 0)}/{int(payload.get('realtime_light_count') or 0)} | "
            f"材质={int(payload.get('material_count') or 0)} | "
            f"剩余={float(payload.get('remaining_seconds') or 0):.0f}s"
        )
        self._append_runner_log(runner_log_path, "PROGRESS", message)
        summary["progress_log_last_at"] = now.isoformat() + "Z"
        summary["progress_log_last_phase"] = phase
        summary["progress_log_last_sample_bucket"] = sample_bucket
        task.result_summary = summary

    def reconcile_project_tasks(self, project_id: int) -> None:
        tasks = (
            self.db.query(TestTask)
            .filter(TestTask.project_id == project_id)
            .filter(TestTask.status.in_([
                TestTaskStatus.RUNNING.value,
                TestTaskStatus.QUEUED.value,
                TestTaskStatus.PENDING.value,
            ]))
            .all()
        )
        for task in tasks:
            session = self._find_task_session(task)
            self._sync_completed_task_from_session(task, session)
            self._sync_stale_task(task, session)

    def _sync_stale_task(self, task: TestTask, session: TestSession | None) -> None:
        if self._task_status_value(task.status) not in {
            TestTaskStatus.RUNNING.value,
            TestTaskStatus.QUEUED.value,
            TestTaskStatus.PENDING.value,
        }:
            return

        config = dict(task.config or {})
        pid = self._int_or_none(config.get("process_id"))
        elapsed = self._duration_seconds(task.started_at, datetime.utcnow())
        expected = (
            float(config.get("frame_rate_duration_seconds") or 30)
            + float(config.get("metrics_duration_seconds") or 30)
            + 180
        )
        process_missing = pid is not None and not self._process_exists(pid)
        task_timed_out = elapsed > expected
        if not (process_missing or task_timed_out):
            return

        reason = "Unity 进程已不存在，任务未完成结果上传" if process_missing else "Unity 测试长时间无结果，已自动结束残留任务"
        task.status = TestTaskStatus.FAILED.value
        task.error_message = reason
        task.completed_at = datetime.utcnow()
        if task.started_at:
            task.duration_seconds = self._duration_seconds(task.started_at, task.completed_at)
        if session and self._session_status_value(session.status) in {
            TestSessionStatus.RUNNING.value,
            TestSessionStatus.PENDING.value,
        }:
            session.status = TestSessionStatus.FAILED.value
            session.ended_at = task.completed_at
            if session.started_at:
                session.duration_seconds = self._duration_seconds(session.started_at, session.ended_at)
        self.db.commit()
        self.db.refresh(task)
        if session:
            self.db.refresh(session)

    def _process_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _duration_seconds(self, start: datetime | None, end: datetime | None) -> float:
        normalized_start = to_utc_naive(start)
        normalized_end = to_utc_naive(end)
        if not normalized_start or not normalized_end:
            return 0
        return max(0.0, (normalized_end - normalized_start).total_seconds())

    def _resolve_backend_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = self.backend_root / path
        return path

    def _load_resource_items(self, kind: str) -> list[dict[str, Any]]:
        root = self.resource_root / kind
        items: list[dict[str, Any]] = []
        if root.exists():
            for path in sorted(root.glob("*.json")):
                with path.open("r", encoding="utf-8") as file:
                    item = json.load(file)
                item.setdefault("id", path.stem)
                item["_config_path"] = str(path)
                items.append(item)

        settings_service = SystemSettingsService()
        if kind == "unity_engines":
            configured_engine, _ = settings_service.get_unity_resources()
            if configured_engine:
                items = [item for item in items if item.get("id") != configured_engine.get("id")]
                items.insert(0, configured_engine)
        elif kind == "unity_projects":
            configured_scenes = settings_service.get_unity_scene_resources()
            if configured_scenes:
                configured_ids = {item.get("id") for item in configured_scenes}
                legacy_ids = {"system-settings-scene", *configured_ids}
                items = [item for item in items if item.get("id") not in legacy_ids]
                items = configured_scenes + items
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

        packages_lock = project_path / "Packages" / "packages-lock.json"
        if packages_lock.exists():
            try:
                with packages_lock.open("r", encoding="utf-8-sig") as file:
                    lock_data = json.load(file)
                if lock_data.get("dependencies", {}).pop(package_name, None) is not None:
                    with packages_lock.open("w", encoding="utf-8") as file:
                        json.dump(lock_data, file, ensure_ascii=False, indent=2)
                        file.write("\n")
            except (OSError, json.JSONDecodeError):
                pass

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
        scope_bundle: dict[str, Any],
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
            "test_scope": scope_bundle["test_scope"],
            "execution_plan": scope_bundle["execution_plan"],
            "test_scope_summary": scope_bundle["test_scope_summary"],
            "quality_checks": scope_bundle["quality_checks"],
            "quality_metric_checks": scope_bundle["quality_metric_checks"],
            "metric_checks": scope_bundle["metric_checks"],
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
        scope_bundle: dict[str, Any],
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
        progress_url = f"{settings.UNITY_RUNNER_PLATFORM_BASE_URL.rstrip('/')}/unity-runner/progress/{task.id}"

        metric_checks = scope_bundle["metric_checks"]
        quality_checks = scope_bundle["quality_checks"]
        quality_metric_checks = scope_bundle["quality_metric_checks"]
        collector_flags = scope_bundle["execution_plan"]["collector_flags"]
        payload = {
            "taskId": task.id,
            "platformSessionId": session.id,
            "sessionName": session.name,
            "projectId": session.project_id,
            "sceneId": session.scene_id or 0,
            "projectName": (session.config or {}).get("platform_project_name", ""),
            "platformBaseUrl": settings.UNITY_RUNNER_PLATFORM_BASE_URL,
            "uploadUrl": upload_url,
            "progressUrl": progress_url,
            "deviceToken": settings.DEVICE_TOKEN,
            "unityEnginePath": engine.get("executable_path"),
            "unityProjectPath": scene.get("project_path"),
            "unityScenePath": scene.get("scene_path"),
            "collectInterval": collect_interval,
            "frameRateDurationSeconds": frame_rate_duration_seconds,
            "metricsDurationSeconds": metrics_duration_seconds,
            "testScopeVersion": scope_bundle["test_scope"].get("schema_version", 1),
            "requestedMetricIds": scope_bundle["test_scope_summary"]["selected_ids"],
            "supportMetricIds": scope_bundle["execution_plan"].get("support_metric_ids", []),
            "collectFrameRate": collector_flags.get("frame_rate", False),
            "collectFrameTime": collector_flags.get("frame_time", False),
            "collectCpuUsage": collector_flags.get("cpu", False),
            "collectGpuUsage": collector_flags.get("gpu", False),
            "collectMemory": collector_flags.get("memory", False),
            "collectDeviceInfo": collector_flags.get("device_info", False),
            "collectRenderingStats": collector_flags.get("rendering_stats", False),
            "collectRenderQuality": collector_flags.get("render_quality", False),
            "enableNetworkUpload": True,
            "autoCreateSession": False,
            "autoStart": True,
            "quitOnComplete": True,
            "forceAutoFlythroughOnStart": True,
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
        runner_log_path: Path | None = None,
    ) -> subprocess.Popen | None:
        project_path = Path(scene["project_path"])
        if self._is_project_open(project_path):
            self._ensure_existing_editor_plugin_current(scene, runner_log_path)
            self._dispatch_to_existing_editor(project_path, task_config_path)
            return None

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

        return subprocess.Popen(
            command,
            cwd=str(self.backend_root),
            env=self._unity_process_environment(),
            start_new_session=os.name != "nt",
        )

    def _ensure_existing_editor_plugin_current(
        self,
        scene: dict[str, Any],
        runner_log_path: Path | None,
        timeout_seconds: float = 60.0,
    ) -> None:
        package_value = scene.get("collector_package_path")
        if not package_value:
            return

        package_path = Path(package_value)
        project_path = Path(scene["project_path"])
        source_mtime = self._latest_plugin_source_mtime(package_path)
        if source_mtime is None:
            return

        script_assemblies = project_path / "Library" / "ScriptAssemblies"
        runtime_assembly = script_assemblies / "XRDataCollector.Runtime.dll"
        editor_assembly = script_assemblies / "XRDataCollector.Editor.dll"
        assembly_mtime = min(
            runtime_assembly.stat().st_mtime if runtime_assembly.exists() else 0.0,
            editor_assembly.stat().st_mtime if editor_assembly.exists() else 0.0,
        )
        if assembly_mtime >= source_mtime:
            return

        marker_path = project_path / "Assets" / "XRDataCollectorGenerated" / "Editor" / "PackageRefreshMarker.cs"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_content = (
            "// Auto-generated by XR Test Platform to refresh the local collector package.\n"
            "namespace XRDataCollectorGenerated\n"
            "{\n"
            f'    internal static class PackageRefreshMarker {{ internal const string SourceTimestamp = "{source_mtime:.6f}"; }}\n'
            "}\n"
        )
        marker_path.write_text(marker_content, encoding="utf-8")
        refresh_started_at = marker_path.stat().st_mtime
        self._append_runner_log(runner_log_path, "INFO", "检测到 Unity 插件程序集落后于源码，等待 Editor 刷新并重新编译。")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            runtime_mtime = runtime_assembly.stat().st_mtime if runtime_assembly.exists() else 0.0
            editor_mtime = editor_assembly.stat().st_mtime if editor_assembly.exists() else 0.0
            if runtime_mtime >= refresh_started_at and editor_mtime >= refresh_started_at:
                self._append_runner_log(runner_log_path, "INFO", "Unity 插件已刷新并重新编译，开始投递测试任务。")
                return
            time.sleep(0.5)

        raise RuntimeError(
            "Unity 插件源码已更新，但当前打开的 Editor 未在 60 秒内完成重新编译。"
            "请检查 Unity Console 编译错误，或关闭 Unity 后重新启动测试。"
        )

    @staticmethod
    def _latest_plugin_source_mtime(package_path: Path) -> float | None:
        if not package_path.is_dir():
            return None
        mtimes = [
            path.stat().st_mtime
            for path in package_path.rglob("*")
            if path.is_file() and path.suffix.lower() in {".cs", ".asmdef", ".json"}
        ]
        return max(mtimes) if mtimes else None

    def _is_project_open(self, project_path: Path) -> bool:
        lock_path = project_path / "Temp" / "UnityLockfile"
        if not lock_path.exists():
            return False
        if os.name == "nt":
            return True
        try:
            import fcntl

            with lock_path.open("a") as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    return False
                except BlockingIOError:
                    return True
        except OSError:
            return True

    def _dispatch_to_existing_editor(self, project_path: Path, task_config_path: Path) -> None:
        with task_config_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        payload["quitOnComplete"] = False
        with task_config_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")

        inbox = project_path / "Library" / "XRDataCollector" / "pending-task.json"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        with inbox.open("w", encoding="utf-8") as file:
            json.dump({"configPath": str(task_config_path)}, file, ensure_ascii=False)

    def _request_existing_editor_stop(
        self,
        task_config: dict[str, Any],
        task_id: int,
        runner_log_path: Path | None,
    ) -> None:
        project_path = self._path_or_none(task_config.get("unity_project_path"))
        if not project_path:
            return
        stop_request = project_path / "Library" / "XRDataCollector" / f"stop-task-{task_id}"
        stop_request.parent.mkdir(parents=True, exist_ok=True)
        stop_request.touch()
        self._append_runner_log(runner_log_path, "INFO", "已向当前打开的 Unity Editor 发送停止请求。")

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
            task.duration_seconds = self._duration_seconds(task.started_at, task.completed_at)
        self.db.commit()
        self.db.refresh(task)

    def _sync_failed_task_from_logs(
        self,
        task: TestTask,
        session: TestSession | None,
        lines: list[str],
        runner_log_path: Path | None,
    ) -> None:
        if self._task_status_value(task.status) not in {
            TestTaskStatus.RUNNING.value,
            TestTaskStatus.QUEUED.value,
            TestTaskStatus.PENDING.value,
        }:
            return

        text = "\n".join(lines)
        error_message = next(
            (message for marker, message in self.UNITY_FATAL_LOG_MARKERS.items() if marker in text),
            None,
        )
        if not error_message:
            return

        task.status = TestTaskStatus.FAILED.value
        task.error_message = error_message
        task.completed_at = datetime.utcnow()
        if task.started_at:
            task.duration_seconds = self._duration_seconds(task.started_at, task.completed_at)

        if session and self._session_status_value(session.status) in {
            TestSessionStatus.RUNNING.value,
            TestSessionStatus.PENDING.value,
        }:
            session.status = TestSessionStatus.FAILED.value
            session.ended_at = datetime.utcnow()
            if session.started_at:
                session.duration_seconds = self._duration_seconds(session.started_at, session.ended_at)

        self.db.commit()
        self.db.refresh(task)
        if session:
            self.db.refresh(session)
        self._append_runner_log(runner_log_path, "ERROR", error_message)

    def _unity_process_environment(self) -> dict[str, str]:
        """Return a small UTF-8 environment Unity 2022 can enumerate safely.

        Some desktop shells inject environment values that Mono cannot convert.
        Unity's Bee compiler enumerates every inherited variable, so passing the
        whole backend environment can put the editor into Safe Mode before the
        automation assembly is loaded.
        """
        allowed_keys = {
            "HOME",
            "PATH",
            "TMPDIR",
            "USER",
            "LOGNAME",
            "SHELL",
            "SSH_AUTH_SOCK",
        }
        environment: dict[str, str] = {}
        for key in allowed_keys:
            value = os.environ.get(key)
            if not value:
                continue
            try:
                key.encode("utf-8")
                value.encode("utf-8")
            except UnicodeError:
                continue
            environment[key] = value

        environment.update(
            {
                "LANG": "en_US.UTF-8",
                "LC_ALL": "en_US.UTF-8",
                "LC_CTYPE": "en_US.UTF-8",
            }
        )
        return environment

    def _monitor_unity_process(
        self,
        *,
        process: subprocess.Popen,
        task_id: int,
        session_id: int,
        runner_log_path: Path,
    ) -> None:
        def monitor() -> None:
            def session_completed() -> bool:
                status_db = SessionLocal()
                try:
                    session = status_db.query(TestSession).filter(TestSession.id == session_id).first()
                    return (
                        session is not None
                        and self._session_status_value(session.status) == TestSessionStatus.COMPLETED.value
                    )
                finally:
                    status_db.close()

            return_code = self._wait_for_unity_process_exit(
                process=process,
                session_completed=session_completed,
                runner_log_path=runner_log_path,
            )
            db = SessionLocal()
            try:
                task = db.query(TestTask).filter(TestTask.id == task_id).first()
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if not task:
                    return

                task_status = self._task_status_value(task.status)
                session_status = self._session_status_value(session.status) if session else ""
                if session_status == TestSessionStatus.COMPLETED.value:
                    task.status = TestTaskStatus.COMPLETED.value
                    task.error_message = None
                elif task_status in {
                    TestTaskStatus.RUNNING.value,
                    TestTaskStatus.QUEUED.value,
                    TestTaskStatus.PENDING.value,
                }:
                    task.status = TestTaskStatus.FAILED.value
                    task.error_message = (
                        f"Unity 进程异常退出，退出码 {return_code}"
                        if return_code != 0
                        else "Unity 进程已退出，但未完成结果上传"
                    )
                    if session:
                        session.status = TestSessionStatus.FAILED.value
                        session.ended_at = datetime.utcnow()
                        if session.started_at:
                            session.duration_seconds = self._duration_seconds(session.started_at, session.ended_at)
                else:
                    self._append_runner_log(
                        runner_log_path,
                        "INFO",
                        f"Unity 进程已退出并回收：pid={process.pid}，退出码={return_code}，任务状态={task_status}",
                    )
                    return

                task.completed_at = task.completed_at or datetime.utcnow()
                if task.started_at:
                    task.duration_seconds = self._duration_seconds(task.started_at, task.completed_at)
                db.commit()
                self._append_runner_log(
                    runner_log_path,
                    "INFO" if task.status == TestTaskStatus.COMPLETED.value else "ERROR",
                    f"Unity 进程已退出：pid={process.pid}，退出码={return_code}，任务状态={self._task_status_value(task.status)}",
                )
            finally:
                db.close()

        thread = threading.Thread(
            target=monitor,
            name=f"unity-runner-{task_id}",
            daemon=True,
        )
        thread.start()

    def _wait_for_unity_process_exit(
        self,
        *,
        process: subprocess.Popen,
        session_completed: Callable[[], bool],
        runner_log_path: Path | None,
    ) -> int:
        completed_seen_at: float | None = None

        while True:
            try:
                return process.wait(timeout=self.UNITY_PROCESS_POLL_SECONDS)
            except subprocess.TimeoutExpired:
                pass

            if not session_completed():
                completed_seen_at = None
                continue

            if completed_seen_at is None:
                completed_seen_at = time.monotonic()
                self._append_runner_log(
                    runner_log_path,
                    "INFO",
                    "测试结果已完成上传，等待 Unity Editor 正常退出。",
                )
                continue

            if time.monotonic() - completed_seen_at < self.UNITY_COMPLETED_EXIT_GRACE_SECONDS:
                continue

            self._append_runner_log(
                runner_log_path,
                "WARN",
                "Unity Editor 在结果上传完成后仍未退出，疑似卡在原生关闭流程，开始回收冷启动进程。",
            )
            self._terminate_process(process.pid, runner_log_path)
            try:
                return process.wait(timeout=self.UNITY_TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                self._append_runner_log(
                    runner_log_path,
                    "WARN",
                    "Unity Editor 未响应终止信号，开始强制回收冷启动进程。",
                )
                self._terminate_process(process.pid, runner_log_path, force=True)
                try:
                    return process.wait(timeout=self.UNITY_FORCE_KILL_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    self._append_runner_log(
                        runner_log_path,
                        "ERROR",
                        "Unity 冷启动进程强制回收后仍未结束，停止等待并保留系统级诊断信息。",
                    )
                    return -int(getattr(signal, "SIGKILL", 9))

    def _terminate_process(self, pid: int, runner_log_path: Path | None, *, force: bool = False) -> bool:
        try:
            if os.name == "nt":
                command = ["taskkill", "/PID", str(pid), "/T"]
                if force:
                    command.append("/F")
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    self._append_runner_log(runner_log_path, "INFO", f"Unity 进程已终止：pid={pid}")
                else:
                    detail = (result.stderr or result.stdout or "").strip()
                    self._append_runner_log(runner_log_path, "WARN", f"终止进程返回非零状态：pid={pid}，{detail}")
                    return False
            else:
                signal_value = signal.SIGKILL if force else signal.SIGTERM
                process_group_id = os.getpgid(pid)
                if process_group_id != os.getpgrp():
                    os.killpg(process_group_id, signal_value)
                else:
                    os.kill(pid, signal_value)
                signal_name = "SIGKILL" if force else "SIGTERM"
                self._append_runner_log(
                    runner_log_path,
                    "INFO",
                    f"Unity 冷启动进程组已发送 {signal_name}：pid={pid}",
                )
            return True
        except Exception as exc:
            self._append_runner_log(runner_log_path, "WARN", f"终止 Unity 进程失败：pid={pid}，{exc}")
            return False

    def _default_unity_editor_log_path(self) -> Path | None:
        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA")
            if not local_app_data:
                return None
            return Path(local_app_data) / "Unity" / "Editor" / "Editor.log"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Logs" / "Unity" / "Editor.log"
        return Path.home() / ".config" / "unity3d" / "Editor.log"

    def _read_log_tail(self, path: Path, max_lines: int = 4000) -> list[str]:
        if not path.exists():
            return []
        try:
            with path.open("rb") as file:
                file.seek(0, os.SEEK_END)
                size = file.tell()
                if size <= 0:
                    return []
                chunk_size = min(size, 768 * 1024)
                file.seek(-chunk_size, os.SEEK_END)
                data = file.read().decode("utf-8", errors="replace")
            return data.splitlines()[-max_lines:]
        except Exception:
            return self._read_log_lines(path)[-max_lines:]

    def _scope_editor_log_to_task(
        self,
        lines: list[str],
        *,
        task_id: int,
        session_id: int | None,
    ) -> list[str]:
        anchors = [
            f"任务 {task_id}",
            f"task {task_id}",
            f"taskId={task_id}",
            f'"taskId": {task_id}',
            f'"taskId":{task_id}',
        ]
        if session_id is not None:
            anchors.extend(
                [
                    f"平台会话 {session_id}",
                    f"platformSessionId={session_id}",
                    f'"platformSessionId": {session_id}',
                    f'"platformSessionId":{session_id}',
                ]
            )

        anchor_idx = -1
        for idx, line in enumerate(lines):
            if any(marker in line for marker in anchors):
                anchor_idx = idx
        if anchor_idx < 0:
            return []
        return lines[anchor_idx:]

    def _read_editor_log_for_task(self, *, task_id: int, session_id: int | None) -> list[str]:
        editor_log_path = self._default_unity_editor_log_path()
        if not editor_log_path:
            return []
        tail_lines = self._read_log_tail(editor_log_path)
        return self._scope_editor_log_to_task(tail_lines, task_id=task_id, session_id=session_id)

    def _missing_unity_log_lines(self, launch_mode: str) -> list[str]:
        if launch_mode == "existing_editor":
            return [
                "──────── Unity 插件（热启动）────────",
                "任务在已打开的 Unity Editor 中执行；插件日志写入本机 Editor.log / Unity Console。",
                "采集进度与指标请以上方 Runner 日志为准。",
            ]
        return ["Unity 日志尚未生成，等待编辑器启动。"]

    def _read_log_lines(self, path: Path | None) -> list[str]:
        if not path or not path.exists():
            return []
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return path.read_text(errors="replace").splitlines()

    def _filter_unity_log_lines(self, lines: list[str], limit: int) -> list[str]:
        if not lines:
            return []

        priority: list[str] = []
        warnings: list[str] = []
        for line in lines:
            if any(marker in line for marker in self.PLUGIN_LOG_MARKERS):
                priority.append(line)
                continue
            upper = line.upper()
            if any(token in upper for token in ("ERROR", "EXCEPTION", "ASSERT", "WARNING", "TRACEBACK")):
                warnings.append(line)

        merged = priority + warnings[-30:]
        if len(merged) < 12:
            fallback_lines = [
                line
                for line in lines
                if not any(marker in line for marker in self.UNITY_LOG_NOISE_MARKERS)
            ]
            merged.extend(fallback_lines[-min(40, limit):])

        deduped: list[str] = []
        seen: set[str] = set()
        for line in merged:
            if line in seen:
                continue
            seen.add(line)
            deduped.append(line)
        return deduped[-limit:]

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
            "is_default": item.get("is_default", False),
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
