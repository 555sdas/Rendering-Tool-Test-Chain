"""多场景连续测试编排服务。"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.project import Project
from app.models.test_batch import TestBatch, TestBatchItem, TestBatchItemStatus, TestBatchStatus
from app.models.test_session import TestSession, TestSessionStatus
from app.models.test_task import TestTask, TestTaskStatus
from app.services.system_settings_service import SystemSettingsService
from app.services.test_scope_service import TestScopeService
from app.services.unity_batch_state import (
    TERMINAL_BATCH_STATUSES,
    compute_allowed_actions,
    compute_overall_progress,
    derive_batch_status_from_items,
    summarize_batch_items,
)
from app.services.unity_project_lease_service import UnityProjectLeaseService
from app.services.unity_runner_service import UnityRunnerService
from app.utils.session_display import get_session_scene_display_name


settings = get_settings()

MAX_SCENES = 20
MIN_SCENES = 2
SCENE_TRANSITION_ALLOWANCE = 30
UPLOAD_ALLOWANCE_PER_SCENE = 60
MAX_TOTAL_SECONDS = 4 * 3600
ORCHESTRATION_SCHEMA_VERSION = 1


class UnityBatchService:
    def __init__(self, db: Session):
        self.db = db
        self.runner = UnityRunnerService(db)
        self.lease_service = UnityProjectLeaseService(db)

    def list_batches(
        self,
        *,
        project_id: int | None = None,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        query = self.db.query(TestBatch)
        if project_id:
            query = query.filter(TestBatch.project_id == project_id)
        if status_filter:
            query = query.filter(TestBatch.status == status_filter)
        total = query.count()
        rows = query.order_by(TestBatch.created_at.desc()).offset(skip).limit(limit).all()
        return {"total": total, "items": [self._batch_summary(batch) for batch in rows]}

    def get_batch(self, batch_id: int) -> dict[str, Any]:
        batch = self._get_batch(batch_id)
        return self._batch_detail(batch)

    def get_active_batch_for_project(self, project_id: int) -> dict[str, Any] | None:
        batch = (
            self.db.query(TestBatch)
            .filter(TestBatch.project_id == project_id)
            .filter(TestBatch.status.in_([TestBatchStatus.PENDING.value, TestBatchStatus.RUNNING.value, TestBatchStatus.AWAITING_USER_DECISION.value]))
            .order_by(TestBatch.created_at.desc())
            .first()
        )
        return self._batch_detail(batch) if batch else None

    def reconcile_active_batches(self) -> dict[str, int]:
        """Reconcile persisted batches after a backend restart."""
        purged_leases = self.lease_service.purge_expired()
        failed_batches = 0
        active_statuses = [
            TestBatchStatus.PENDING.value,
            TestBatchStatus.RUNNING.value,
            TestBatchStatus.AWAITING_USER_DECISION.value,
        ]
        batches = self.db.query(TestBatch).filter(TestBatch.status.in_(active_statuses)).all()
        for batch in batches:
            parent_task = self.db.query(TestTask).filter(TestTask.id == batch.parent_task_id).first()
            parent_config = dict(parent_task.config or {}) if parent_task else {}
            launch_mode = parent_config.get("launch_mode")
            pid = self.runner._int_or_none(parent_config.get("process_id"))
            process_missing = launch_mode == "new_editor" and (pid is None or not self.runner._process_exists(pid))
            if parent_task is not None and not process_missing:
                self.lease_service.heartbeat(batch.unity_project_path)
                continue

            reason = "后端重启对账发现父任务不存在" if parent_task is None else "后端重启对账发现 Unity 进程已不存在"
            self._mark_batch_failed_after_reconcile(batch, parent_task, reason)
            failed_batches += 1

        self.db.commit()
        return {"failed_batches": failed_batches, "purged_leases": purged_leases}

    def start_batch(
        self,
        *,
        project_id: int,
        unity_engine_id: str,
        scenes: list[dict[str, Any]],
        batchmode: bool,
        ensure_plugin: bool,
        creator_id: int,
    ) -> dict[str, Any]:
        self._validate_start_payload(scenes)
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        engine = self.runner._get_resource_item("unity_engines", unity_engine_id)
        self.runner._validate_engine(engine)

        resolved_scenes: list[dict[str, Any]] = []
        project_path: str | None = None
        for entry in scenes:
            scene = self.runner._get_resource_item("unity_projects", entry["scene_resource_id"])
            self.runner._validate_scene(scene)
            normalized = UnityProjectLeaseService.normalize_project_path(scene["project_path"])
            if project_path is None:
                project_path = normalized
            elif project_path != normalized:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所有场景必须属于同一 Unity 工程")
            scope_bundle = self.runner.resolve_scope_bundle(test_scope=entry.get("test_scope"))
            resolved_scenes.append(
                {
                    "scene": scene,
                    "scope_bundle": scope_bundle,
                    "collect_interval": float(entry["collect_interval"]),
                    "frame_rate_duration_seconds": float(entry["frame_rate_duration_seconds"]),
                    "metrics_duration_seconds": float(entry["metrics_duration_seconds"]),
                }
            )

        if ensure_plugin:
            self.runner._ensure_plugin_manifest(resolved_scenes[0]["scene"])

        total_seconds = sum(
            item["frame_rate_duration_seconds"] + item["metrics_duration_seconds"] + SCENE_TRANSITION_ALLOWANCE + UPLOAD_ALLOWANCE_PER_SCENE
            for item in resolved_scenes
        )
        if total_seconds > MAX_TOTAL_SECONDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="编排预计总时长超过 4 小时，请减少场景或缩短采集时长")

        assert project_path is not None
        project_key = UnityProjectLeaseService.project_key(project_path)

        parent_task = TestTask(
            name=f"{project.name} - 多场景编排 ({len(resolved_scenes)} 场景)",
            description="Unity 多场景连续测试父任务",
            status=TestTaskStatus.RUNNING.value,
            task_type="unity_multi_scene_orchestration",
            priority=0,
            project_id=project_id,
            scene_id=None,
            creator_id=creator_id,
            config={
                "run_mode": "multi_scene",
                "unity_project_path": project_path,
            },
            started_at=datetime.utcnow(),
        )
        self.db.add(parent_task)
        self.db.flush()

        batch = TestBatch(
            project_id=project_id,
            creator_id=creator_id,
            parent_task_id=parent_task.id,
            status=TestBatchStatus.PENDING.value,
            current_scene_index=0,
            scene_total=len(resolved_scenes),
            unity_project_path=project_path,
            unity_project_key=project_key,
            config={
                "unity_engine_id": unity_engine_id,
                "batchmode": batchmode,
                "ensure_plugin": ensure_plugin,
                "schema_version": ORCHESTRATION_SCHEMA_VERSION,
            },
            result_summary={"scene_total": len(resolved_scenes)},
            decision_version=0,
        )
        self.db.add(batch)
        self.db.flush()
        parent_task.config = {
            **(parent_task.config or {}),
            "batch_id": batch.id,
        }

        lease = self.lease_service.acquire(
            project_path=project_path,
            owner_type="multi_scene",
            owner_id=batch.id,
            parent_task_id=parent_task.id,
        )

        items: list[TestBatchItem] = []
        scene_run_payloads: list[dict[str, Any]] = []
        runner_log_path: Path | None = None
        try:
            for index, resolved in enumerate(resolved_scenes):
                scene = resolved["scene"]
                scene_asset = self.runner._ensure_scene_asset(project_id, scene)
                display_name = scene.get("name") or Path(scene.get("scene_path", "")).stem
                item_config = {
                    "test_scope": resolved["scope_bundle"]["test_scope"],
                    "execution_plan": resolved["scope_bundle"]["execution_plan"],
                    "test_scope_summary": resolved["scope_bundle"]["test_scope_summary"],
                    "collect_interval": resolved["collect_interval"],
                    "frame_rate_duration_seconds": resolved["frame_rate_duration_seconds"],
                    "metrics_duration_seconds": resolved["metrics_duration_seconds"],
                }
                item = TestBatchItem(
                    batch_id=batch.id,
                    scene_index=index,
                    scene_resource_id=scene["id"],
                    scene_id=scene_asset.id if scene_asset else None,
                    scene_display_name=display_name,
                    unity_scene_path=scene["scene_path"],
                    status=TestBatchItemStatus.PENDING.value,
                    attempt_count=0,
                    config=item_config,
                    attempt_history=[],
                )
                self.db.add(item)
                self.db.flush()

                attempt = self._create_scene_attempt(
                    batch=batch,
                    item=item,
                    project=project,
                    engine=engine,
                    scene=scene,
                    scene_asset=scene_asset,
                    scope_bundle=resolved["scope_bundle"],
                    collect_interval=resolved["collect_interval"],
                    frame_rate_duration_seconds=resolved["frame_rate_duration_seconds"],
                    metrics_duration_seconds=resolved["metrics_duration_seconds"],
                    creator_id=creator_id,
                    parent_task=parent_task,
                )
                items.append(item)
                scene_run_payloads.append(attempt["scene_payload"])

            orch_path, unity_log_path, runner_log_path = self._write_orchestration_config(
                batch=batch,
                parent_task=parent_task,
                engine=engine,
                project=project,
                scene_payloads=scene_run_payloads,
                batchmode=batchmode,
            )

            process = self.runner._launch_unity(
                engine=engine,
                scene=resolved_scenes[0]["scene"],
                task_config_path=orch_path,
                log_path=unity_log_path,
                runner_log_path=runner_log_path,
                batchmode=batchmode,
            )

            parent_config = dict(parent_task.config or {})
            parent_config.update(
                {
                    "process_id": process.pid if process else None,
                    "launch_mode": "new_editor" if process else "existing_editor",
                    "orchestration_config_path": str(orch_path),
                    "unity_log_path": str(unity_log_path),
                    "runner_log_path": str(runner_log_path),
                    "unity_engine_id": unity_engine_id,
                }
            )
            parent_task.config = parent_config
            batch.status = TestBatchStatus.RUNNING.value
            batch.started_at = datetime.utcnow()
            if items:
                items[0].status = TestBatchItemStatus.RUNNING.value
                items[0].started_at = datetime.utcnow()

            self.runner._append_runner_log(
                runner_log_path,
                "INFO",
                f"启动多场景编排：batch={batch.id}, parent_task={parent_task.id}, scenes={len(items)}",
            )
            self.db.commit()
            self.db.refresh(batch)

            if process:
                self.runner._monitor_unity_process(
                    process=process,
                    task_id=parent_task.id,
                    session_id=0,
                    runner_log_path=runner_log_path,
                    batch_id=batch.id,
                )
            else:
                self.runner._append_runner_log(runner_log_path, "INFO", "编排任务已投递到当前打开的 Unity Editor。")

            return self._batch_detail(batch)
        except Exception as exc:
            batch.status = TestBatchStatus.FAILED.value
            batch.completed_at = datetime.utcnow()
            parent_task.status = TestTaskStatus.FAILED.value
            parent_task.error_message = str(exc)
            parent_task.completed_at = datetime.utcnow()
            for item in items:
                item.status = TestBatchItemStatus.CANCELLED.value
            self.lease_service.release(project_path)
            self.runner._append_runner_log(runner_log_path, "ERROR", f"启动多场景编排失败：{exc}")
            self.db.commit()
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"启动多场景编排失败：{exc}") from exc

    def apply_decision(
        self,
        *,
        batch_id: int,
        action: str,
        expected_item_id: int,
        expected_scene_index: int,
        decision_version: int,
    ) -> dict[str, Any]:
        batch = self._get_batch(batch_id)
        if batch.status != TestBatchStatus.AWAITING_USER_DECISION.value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前批次不在等待用户决策状态")
        if batch.decision_version != decision_version:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="决策版本已过期，请刷新后重试")

        item = self._get_item(batch, expected_item_id, expected_scene_index)
        if action == "abort":
            return self.stop_batch(batch_id)

        if action == "skip":
            item.status = TestBatchItemStatus.SKIPPED.value
            item.completed_at = datetime.utcnow()
            batch.decision_version += 1
            batch.status = TestBatchStatus.RUNNING.value
            batch.current_scene_index = min(item.scene_index + 1, batch.scene_total - 1)
            self._write_command_file(batch, action="skip", item=item)
            self._refresh_batch_summary(batch)
            self.db.commit()
            return self._batch_detail(batch)

        if action == "retry":
            project = self.db.query(Project).filter(Project.id == batch.project_id).first()
            engine = self.runner._get_resource_item("unity_engines", (batch.config or {}).get("unity_engine_id"))
            scene = self.runner._get_resource_item("unity_projects", item.scene_resource_id)
            scene_asset = self.runner._ensure_scene_asset(batch.project_id, scene)
            parent_task = self.db.query(TestTask).filter(TestTask.id == batch.parent_task_id).first()
            scope_bundle = self.runner.resolve_scope_bundle(test_scope=(item.config or {}).get("test_scope"))
            attempt = self._create_scene_attempt(
                batch=batch,
                item=item,
                project=project,
                engine=engine,
                scene=scene,
                scene_asset=scene_asset,
                scope_bundle=scope_bundle,
                collect_interval=float((item.config or {}).get("collect_interval", 1)),
                frame_rate_duration_seconds=float((item.config or {}).get("frame_rate_duration_seconds", 30)),
                metrics_duration_seconds=float((item.config or {}).get("metrics_duration_seconds", 30)),
                creator_id=batch.creator_id,
                parent_task=parent_task,
            )
            self._rewrite_orchestration_for_retry(batch, parent_task, attempt["scene_payload"], item.scene_index)
            item.status = TestBatchItemStatus.RUNNING.value
            item.error_message = None
            batch.status = TestBatchStatus.RUNNING.value
            batch.current_scene_index = item.scene_index
            batch.decision_version += 1
            self._write_command_file(batch, action="retry", item=item, retry_scene_config=attempt["scene_payload"])
            self.db.commit()
            return self._batch_detail(batch)

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的决策动作")

    def stop_batch(self, batch_id: int) -> dict[str, Any]:
        batch = self._get_batch(batch_id)
        if batch.status in TERMINAL_BATCH_STATUSES:
            return self._batch_detail(batch)

        parent_task = self.db.query(TestTask).filter(TestTask.id == batch.parent_task_id).first()
        parent_config = dict(parent_task.config or {}) if parent_task else {}
        runner_log_path = self.runner._path_or_none(parent_config.get("runner_log_path"))

        batch.status = TestBatchStatus.CANCELLED.value
        batch.completed_at = datetime.utcnow()
        if parent_task:
            parent_task.status = TestTaskStatus.CANCELLED.value
            parent_task.completed_at = datetime.utcnow()
            # The orchestration runner polls the parent-task stop file in every
            # state, including active collection. Cold-start processes are
            # reclaimed by the existing process watchdog if graceful shutdown
            # does not finish within its grace period.
            self.runner._request_existing_editor_stop(parent_config, parent_task.id, runner_log_path)
            self.runner._request_orchestration_abort(batch.id, parent_config)

        for item in batch.items:
            if item.status in {TestBatchItemStatus.PENDING.value, TestBatchItemStatus.RUNNING.value, TestBatchItemStatus.AWAITING_USER_DECISION.value}:
                item.status = TestBatchItemStatus.CANCELLED.value
                if item.current_session_id:
                    session = self.db.query(TestSession).filter(TestSession.id == item.current_session_id).first()
                    if session and session.status == TestSessionStatus.RUNNING.value:
                        session.status = TestSessionStatus.CANCELLED.value
                        session.ended_at = datetime.utcnow()

        self.lease_service.release(batch.unity_project_path)
        self._refresh_batch_summary(batch)
        self.runner._append_runner_log(runner_log_path, "INFO", f"多场景编排已终止：batch={batch.id}")
        self.db.commit()
        return self._batch_detail(batch)

    def on_scene_upload_completed(self, session: TestSession) -> None:
        config = session.config or {}
        batch_item_id = config.get("batch_item_id")
        if not batch_item_id:
            return
        item = self.db.query(TestBatchItem).filter(TestBatchItem.id == int(batch_item_id)).first()
        if not item:
            return
        batch = self.db.query(TestBatch).filter(TestBatch.id == item.batch_id).first()
        if not batch:
            return

        item.status = TestBatchItemStatus.COMPLETED.value
        item.completed_at = datetime.utcnow()
        item.error_message = None
        if item.current_task_id:
            task = self.db.query(TestTask).filter(TestTask.id == item.current_task_id).first()
            if task:
                task.status = TestTaskStatus.COMPLETED.value
                task.completed_at = datetime.utcnow()

        next_index = item.scene_index + 1
        if next_index < batch.scene_total:
            batch.current_scene_index = next_index
            batch.status = TestBatchStatus.RUNNING.value
            next_item = self._item_by_index(batch, next_index)
            if next_item and next_item.status == TestBatchItemStatus.PENDING.value:
                next_item.status = TestBatchItemStatus.RUNNING.value
                next_item.started_at = datetime.utcnow()
        else:
            batch.status = derive_batch_status_from_items(batch.items)
            batch.completed_at = datetime.utcnow()
            self.lease_service.release(batch.unity_project_path)
            parent_task = self.db.query(TestTask).filter(TestTask.id == batch.parent_task_id).first()
            if parent_task:
                parent_task.status = TestTaskStatus.COMPLETED.value
                parent_task.completed_at = datetime.utcnow()

        self._refresh_batch_summary(batch)
        self.lease_service.heartbeat(batch.unity_project_path)
        self.db.flush()

    def on_progress_event(self, parent_task: TestTask, payload: dict[str, Any]) -> None:
        batch_id = payload.get("batch_id") or (parent_task.config or {}).get("batch_id")
        if not batch_id:
            return
        batch = self.db.query(TestBatch).filter(TestBatch.id == int(batch_id)).first()
        if not batch:
            return

        batch_status = payload.get("batch_status")
        if batch_status == "awaiting_user_decision":
            batch.status = TestBatchStatus.AWAITING_USER_DECISION.value
            item_id = payload.get("batch_item_id")
            if item_id:
                item = self.db.query(TestBatchItem).filter(TestBatchItem.id == int(item_id)).first()
                if item:
                    item.status = TestBatchItemStatus.AWAITING_USER_DECISION.value
                    item.error_message = payload.get("error_message") or payload.get("message")
            batch.decision_version += 1

        scene_index = payload.get("scene_index")
        if isinstance(scene_index, int):
            batch.current_scene_index = scene_index

        summary = dict(batch.result_summary or {})
        summary["latest_progress"] = payload
        scene_progress = float(payload.get("scene_progress") or payload.get("progress") or 0)
        item_rows = [
            {"config": item.config, "status": item.status}
            for item in sorted(batch.items, key=lambda row: row.scene_index)
        ]
        summary["overall_progress"] = compute_overall_progress(
            item_rows,
            current_scene_index=batch.current_scene_index,
            current_scene_progress=scene_progress,
        )
        batch.result_summary = summary
        self.lease_service.heartbeat(batch.unity_project_path)
        self.db.flush()

    def _validate_start_payload(self, scenes: list[dict[str, Any]]) -> None:
        if len(scenes) < MIN_SCENES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"多场景编排至少需要 {MIN_SCENES} 个场景")
        if len(scenes) > MAX_SCENES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"多场景编排最多支持 {MAX_SCENES} 个场景")
        seen: set[str] = set()
        for entry in scenes:
            scene_id = entry.get("scene_resource_id")
            if not scene_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 scene_resource_id")
            if scene_id in seen:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="编排中不能包含重复场景")
            seen.add(scene_id)
            if entry.get("test_scope"):
                TestScopeService.validate_scope(entry["test_scope"])

    def _mark_batch_failed_after_reconcile(
        self,
        batch: TestBatch,
        parent_task: TestTask | None,
        reason: str,
    ) -> None:
        now = datetime.utcnow()
        batch.status = TestBatchStatus.FAILED.value
        batch.completed_at = now
        if parent_task:
            parent_task.status = TestTaskStatus.FAILED.value
            parent_task.error_message = reason
            parent_task.completed_at = now
        for item in batch.items:
            if item.status not in {
                TestBatchItemStatus.PENDING.value,
                TestBatchItemStatus.RUNNING.value,
                TestBatchItemStatus.UPLOADING.value,
                TestBatchItemStatus.AWAITING_USER_DECISION.value,
            }:
                continue
            item.status = (
                TestBatchItemStatus.FAILED.value
                if item.scene_index == batch.current_scene_index
                else TestBatchItemStatus.CANCELLED.value
            )
            item.error_message = reason
            item.completed_at = now
            if item.current_task_id:
                task = self.db.query(TestTask).filter(TestTask.id == item.current_task_id).first()
                if task and task.status in {
                    TestTaskStatus.PENDING.value,
                    TestTaskStatus.QUEUED.value,
                    TestTaskStatus.RUNNING.value,
                }:
                    task.status = TestTaskStatus.FAILED.value
                    task.error_message = reason
                    task.completed_at = now
            if item.current_session_id:
                session = self.db.query(TestSession).filter(TestSession.id == item.current_session_id).first()
                if session and session.status in {
                    TestSessionStatus.PENDING.value,
                    TestSessionStatus.RUNNING.value,
                }:
                    session.status = TestSessionStatus.FAILED.value
                    session.ended_at = now
        self.lease_service.release(batch.unity_project_path)
        self._refresh_batch_summary(batch)

    def _create_scene_attempt(
        self,
        *,
        batch: TestBatch,
        item: TestBatchItem,
        project: Project,
        engine: dict[str, Any],
        scene: dict[str, Any],
        scene_asset: Any,
        scope_bundle: dict[str, Any],
        collect_interval: float,
        frame_rate_duration_seconds: float,
        metrics_duration_seconds: float,
        creator_id: int | None,
        parent_task: TestTask,
    ) -> dict[str, Any]:
        run_index = self.runner._next_session_index(project.id)
        session_name = f"#{run_index}"
        session_config = SystemSettingsService().attach_scoring_definition_snapshot(
            self.runner._build_session_config(
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
        session_config.update(
            {
                "run_mode": "multi_scene",
                "batch_id": batch.id,
                "batch_item_id": item.id,
                "parent_task_id": parent_task.id,
                "scene_index": item.scene_index,
                "scene_total": batch.scene_total,
                "attempt": item.attempt_count + 1,
                "scene_display_name": item.scene_display_name,
            }
        )

        session = TestSession(
            name=session_name,
            description=f"多场景编排场景：{item.scene_display_name}",
            status=TestSessionStatus.RUNNING.value,
            scene_id=scene_asset.id if scene_asset else None,
            user_id=creator_id,
            project_id=project.id,
            config=session_config,
            started_at=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.flush()

        task = TestTask(
            name=f"{project.name} - {item.scene_display_name} - 多场景子任务",
            description="多场景编排中的单场景尝试",
            status=TestTaskStatus.RUNNING.value,
            task_type="unity_multi_scene_item",
            priority=0,
            project_id=project.id,
            scene_id=session.scene_id,
            creator_id=creator_id,
            config=session_config,
            started_at=datetime.utcnow(),
        )
        self.db.add(task)
        self.db.flush()

        item.attempt_count += 1
        item.current_task_id = task.id
        item.current_session_id = session.id
        history = list(item.attempt_history or [])
        history.append(
            {
                "attempt": item.attempt_count,
                "task_id": task.id,
                "session_id": session.id,
                "status": "running",
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
        )
        item.attempt_history = history

        session_config["test_task_id"] = task.id
        session.config = session_config
        task.config = dict(session_config)

        scene_payload = self._build_scene_run_payload(
            batch=batch,
            item=item,
            task=task,
            session=session,
            project=project,
            engine=engine,
            scene=scene,
            scope_bundle=scope_bundle,
            collect_interval=collect_interval,
            frame_rate_duration_seconds=frame_rate_duration_seconds,
            metrics_duration_seconds=metrics_duration_seconds,
            parent_task=parent_task,
        )
        return {"task": task, "session": session, "scene_payload": scene_payload}

    def _build_scene_run_payload(
        self,
        *,
        batch: TestBatch,
        item: TestBatchItem,
        task: TestTask,
        session: TestSession,
        project: Project,
        engine: dict[str, Any],
        scene: dict[str, Any],
        scope_bundle: dict[str, Any],
        collect_interval: float,
        frame_rate_duration_seconds: float,
        metrics_duration_seconds: float,
        parent_task: TestTask,
    ) -> dict[str, Any]:
        collector_flags = scope_bundle["execution_plan"]["collector_flags"]
        quality_checks = scope_bundle["quality_checks"]
        quality_metric_checks = scope_bundle["quality_metric_checks"]
        base = settings.UNITY_RUNNER_PLATFORM_BASE_URL.rstrip("/")
        return {
            "batchItemId": item.id,
            "sceneIndex": item.scene_index,
            "sceneTotal": batch.scene_total,
            "attempt": item.attempt_count,
            "taskId": task.id,
            "platformSessionId": session.id,
            "sessionName": session.name,
            "sceneId": session.scene_id or 0,
            "projectName": project.name,
            "platformBaseUrl": base,
            "unityScenePath": scene["scene_path"],
            "uploadUrl": f"{base}/data-collection/test-sessions/{session.id}/samples/batch",
            "progressUrl": f"{base}/unity-runner/progress/{parent_task.id}",
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
            "autoStart": False,
            "forceAutoFlythroughOnStart": True,
            "sceneDisplayName": item.scene_display_name,
            "qualityChecks": {
                "lighting": quality_checks.get("lighting", True),
                "materials": quality_checks.get("materials", True),
                "postProcessing": quality_checks.get("post_processing", True),
                "physics": quality_checks.get("physics", True),
            },
            "qualityMetricChecks": self.runner._quality_metric_payload(quality_metric_checks),
        }

    def _write_orchestration_config(
        self,
        *,
        batch: TestBatch,
        parent_task: TestTask,
        engine: dict[str, Any],
        project: Project,
        scene_payloads: list[dict[str, Any]],
        batchmode: bool,
    ) -> tuple[Path, Path, Path]:
        self.runner.task_root.mkdir(parents=True, exist_ok=True)
        self.runner.log_root.mkdir(parents=True, exist_ok=True)
        orch_path = self.runner.task_root / f"unity_batch_{batch.id}_parent_{parent_task.id}.json"
        unity_log_path = self.runner.log_root / f"unity_batch_{batch.id}_parent_{parent_task.id}.unity.log"
        runner_log_path = self.runner.log_root / f"unity_batch_{batch.id}_parent_{parent_task.id}.runner.log"
        base = settings.UNITY_RUNNER_PLATFORM_BASE_URL.rstrip("/")
        payload = {
            "schemaVersion": ORCHESTRATION_SCHEMA_VERSION,
            "runMode": "multi_scene",
            "batchId": batch.id,
            "parentTaskId": parent_task.id,
            "projectId": project.id,
            "unityProjectPath": batch.unity_project_path,
            "progressUrl": f"{base}/unity-runner/progress/{parent_task.id}",
            "deviceToken": settings.DEVICE_TOKEN,
            "quitOnComplete": True,
            "batchmode": batchmode,
            "scenes": scene_payloads,
        }
        with orch_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        try:
            os.chmod(orch_path, 0o600)
        except OSError:
            pass
        return orch_path, unity_log_path, runner_log_path

    def _rewrite_orchestration_for_retry(
        self,
        batch: TestBatch,
        parent_task: TestTask,
        scene_payload: dict[str, Any],
        scene_index: int,
    ) -> None:
        parent_config = dict(parent_task.config or {})
        orch_path = self.runner._path_or_none(parent_config.get("orchestration_config_path"))
        if not orch_path or not orch_path.exists():
            return
        data = json.loads(orch_path.read_text(encoding="utf-8"))
        scenes = list(data.get("scenes") or [])
        if 0 <= scene_index < len(scenes):
            scenes[scene_index] = scene_payload
            data["scenes"] = scenes
            with orch_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")

    def _write_command_file(
        self,
        batch: TestBatch,
        *,
        action: str,
        item: TestBatchItem,
        retry_scene_config: dict[str, Any] | None = None,
    ) -> None:
        project_path = Path(batch.unity_project_path)
        command_dir = project_path / "Library" / "XRDataCollector"
        command_dir.mkdir(parents=True, exist_ok=True)
        command_path = command_dir / f"orchestration-command-{batch.id}.json"
        payload = {
            "schemaVersion": 1,
            "commandId": str(uuid.uuid4()),
            "batchId": batch.id,
            "expectedBatchItemId": item.id,
            "expectedSceneIndex": item.scene_index,
            "decisionVersion": batch.decision_version,
            "action": action,
        }
        if retry_scene_config:
            payload["retrySceneConfig"] = retry_scene_config
        temp_path = command_path.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temp_path.replace(command_path)

    def _refresh_batch_summary(self, batch: TestBatch) -> None:
        summary = summarize_batch_items(batch.items)
        summary["latest_error"] = next(
            (item.error_message for item in sorted(batch.items, key=lambda row: row.scene_index) if item.error_message),
            None,
        )
        batch.result_summary = {**(batch.result_summary or {}), **summary}
        if batch.status not in TERMINAL_BATCH_STATUSES and batch.status != TestBatchStatus.AWAITING_USER_DECISION.value:
            batch.status = derive_batch_status_from_items(batch.items)

    def _batch_summary(self, batch: TestBatch) -> dict[str, Any]:
        return {
            "id": batch.id,
            "project_id": batch.project_id,
            "parent_task_id": batch.parent_task_id,
            "status": batch.status,
            "current_scene_index": batch.current_scene_index,
            "scene_total": batch.scene_total,
            "result_summary": batch.result_summary,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "decision_version": batch.decision_version,
            "run_mode": "multi_scene",
        }

    def _batch_detail(self, batch: TestBatch) -> dict[str, Any]:
        parent_task = self.db.query(TestTask).filter(TestTask.id == batch.parent_task_id).first()
        items = sorted(batch.items, key=lambda row: row.scene_index)
        return {
            "batch": self._batch_summary(batch),
            "parent_task": self.runner._task_response(parent_task) if parent_task else None,
            "items": [self._item_response(item) for item in items],
            "allowed_actions": compute_allowed_actions(batch.status),
            "process_id": (parent_task.config or {}).get("process_id") if parent_task else None,
            "launch_mode": (parent_task.config or {}).get("launch_mode") if parent_task else None,
            "orchestration_config_path": (parent_task.config or {}).get("orchestration_config_path") if parent_task else None,
            "runner_log_path": (parent_task.config or {}).get("runner_log_path") if parent_task else None,
            "unity_log_path": (parent_task.config or {}).get("unity_log_path") if parent_task else None,
        }

    def _item_response(self, item: TestBatchItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "scene_index": item.scene_index,
            "scene_resource_id": item.scene_resource_id,
            "scene_display_name": item.scene_display_name,
            "unity_scene_path": item.unity_scene_path,
            "status": item.status,
            "attempt_count": item.attempt_count,
            "current_task_id": item.current_task_id,
            "current_session_id": item.current_session_id,
            "config": item.config,
            "attempt_history": item.attempt_history or [],
            "error_message": item.error_message,
        }

    def _get_batch(self, batch_id: int) -> TestBatch:
        batch = self.db.query(TestBatch).filter(TestBatch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="多场景编排不存在")
        return batch

    def _get_item(self, batch: TestBatch, item_id: int, scene_index: int) -> TestBatchItem:
        item = self.db.query(TestBatchItem).filter(TestBatchItem.id == item_id, TestBatchItem.batch_id == batch.id).first()
        if not item or item.scene_index != scene_index:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="场景项与当前批次状态不一致")
        return item

    def _item_by_index(self, batch: TestBatch, scene_index: int) -> TestBatchItem | None:
        return next((item for item in batch.items if item.scene_index == scene_index), None)
