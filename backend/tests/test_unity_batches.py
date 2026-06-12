from datetime import datetime, timedelta
from pathlib import Path

from app.models.project import Project
from app.models.test_batch import TestBatch as BatchModel, TestBatchItem as BatchItemModel
from app.models.test_task import TestTask as TaskModel
from app.models.unity_project_lease import UnityProjectLease
from app.services.unity_batch_service import UnityBatchService
from app.services.unity_project_lease_service import UnityProjectLeaseService


def test_multi_scene_scope_bundle_accepts_test_scope_only(db):
    bundle = UnityBatchService(db).runner.resolve_scope_bundle(test_scope=None)

    assert bundle["test_scope"]
    assert bundle["execution_plan"]
    assert bundle["test_scope_summary"]["selected_count"] > 0


def test_start_batch_persists_parent_task_before_foreign_key_batch(db, monkeypatch, tmp_path):
    project = Project(name="Foreign key project")
    db.add(project)
    db.commit()
    service = UnityBatchService(db)
    scenes = {
        "scene-a": {
            "id": "scene-a",
            "name": "Scene A",
            "project_path": str(tmp_path),
            "scene_path": "Assets/A.unity",
        },
        "scene-b": {
            "id": "scene-b",
            "name": "Scene B",
            "project_path": str(tmp_path),
            "scene_path": "Assets/B.unity",
        },
    }
    engine = {"id": "unity-1", "name": "Unity", "version": "test", "executable_path": str(tmp_path / "Unity")}

    monkeypatch.setattr(
        service.runner,
        "_get_resource_item",
        lambda kind, item_id: engine if kind == "unity_engines" else scenes[item_id],
    )
    monkeypatch.setattr(service.runner, "_validate_engine", lambda _engine: None)
    monkeypatch.setattr(service.runner, "_validate_scene", lambda _scene: None)
    monkeypatch.setattr(service, "_write_orchestration_config", lambda **_kwargs: (
        Path(tmp_path / "orchestration.json"),
        Path(tmp_path / "unity.log"),
        Path(tmp_path / "runner.log"),
    ))
    monkeypatch.setattr(service.runner, "_launch_unity", lambda **_kwargs: None)
    monkeypatch.setattr(service.runner, "_append_runner_log", lambda *_args, **_kwargs: None)

    result = service.start_batch(
        project_id=project.id,
        unity_engine_id="unity-1",
        scenes=[
            {
                "scene_resource_id": "scene-a",
                "collect_interval": 1,
                "frame_rate_duration_seconds": 1,
                "metrics_duration_seconds": 1,
            },
            {
                "scene_resource_id": "scene-b",
                "collect_interval": 1,
                "frame_rate_duration_seconds": 1,
                "metrics_duration_seconds": 1,
            },
        ],
        batchmode=False,
        ensure_plugin=False,
        creator_id=None,  # type: ignore[arg-type]
    )

    batch = db.query(BatchModel).one()
    parent_task = db.query(TaskModel).filter(TaskModel.id == batch.parent_task_id).one()
    assert result["batch"]["id"] == batch.id
    assert parent_task.config["batch_id"] == batch.id


def test_unity_batch_start_decision_stop_api_flow(client, auth_headers, monkeypatch):
    state = {"status": "running", "decision_version": 0}
    calls: list[tuple[str, object]] = []

    def detail():
        return {
            "batch": {
                "id": 7,
                "project_id": 1,
                "parent_task_id": 70,
                "status": state["status"],
                "scene_total": 2,
                "decision_version": state["decision_version"],
            },
            "items": [
                {"id": 71, "scene_index": 0, "status": "running"},
                {"id": 72, "scene_index": 1, "status": "pending"},
            ],
            "allowed_actions": ["abort"],
        }

    def start_batch(self, **kwargs):
        calls.append(("start", kwargs))
        return detail()

    def apply_decision(self, **kwargs):
        calls.append(("decision", kwargs))
        state["status"] = "running"
        state["decision_version"] += 1
        return detail()

    def stop_batch(self, batch_id):
        calls.append(("stop", batch_id))
        state["status"] = "cancelled"
        return detail()

    monkeypatch.setattr("app.routers.unity_batches.UnityBatchService.start_batch", start_batch)
    monkeypatch.setattr("app.routers.unity_batches.UnityBatchService.apply_decision", apply_decision)
    monkeypatch.setattr("app.routers.unity_batches.UnityBatchService.stop_batch", stop_batch)

    start_response = client.post(
        "/api/v1/unity-runner/test-batches/start",
        headers=auth_headers,
        json={
            "project_id": 1,
            "unity_engine_id": "unity-1",
            "scenes": [
                {"scene_resource_id": "scene-a"},
                {"scene_resource_id": "scene-b"},
            ],
        },
    )
    assert start_response.status_code == 200
    assert start_response.json()["batch"]["scene_total"] == 2

    state["status"] = "awaiting_user_decision"
    decision_response = client.post(
        "/api/v1/unity-runner/test-batches/7/decision",
        headers=auth_headers,
        json={
            "action": "skip",
            "expected_item_id": 71,
            "expected_scene_index": 0,
            "decision_version": 0,
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["batch"]["decision_version"] == 1

    stop_response = client.post("/api/v1/unity-runner/test-batches/7/stop", headers=auth_headers)
    assert stop_response.status_code == 200
    assert stop_response.json()["batch"]["status"] == "cancelled"
    assert [name for name, _ in calls] == ["start", "decision", "stop"]


def test_unity_batch_start_requires_at_least_two_scenes(client, auth_headers):
    response = client.post(
        "/api/v1/unity-runner/test-batches/start",
        headers=auth_headers,
        json={
            "project_id": 1,
            "unity_engine_id": "unity-1",
            "scenes": [{"scene_resource_id": "scene-a"}],
        },
    )
    assert response.status_code == 422


def test_stop_running_batch_sends_parent_stop_file_instead_of_immediate_kill(db, monkeypatch, tmp_path):
    project = Project(name="Stop project")
    db.add(project)
    db.flush()
    parent_task = TaskModel(
        name="Parent",
        task_type="unity_multi_scene_orchestration",
        status="running",
        project_id=project.id,
        config={
            "launch_mode": "new_editor",
            "process_id": 12345,
            "unity_project_path": str(tmp_path),
        },
    )
    db.add(parent_task)
    db.flush()
    batch = BatchModel(
        project_id=project.id,
        parent_task_id=parent_task.id,
        status="running",
        current_scene_index=0,
        scene_total=1,
        unity_project_path=str(tmp_path),
        unity_project_key=UnityProjectLeaseService.project_key(str(tmp_path)),
    )
    db.add(batch)
    db.flush()
    db.add(
        BatchItemModel(
            batch_id=batch.id,
            scene_index=0,
            scene_resource_id="scene-a",
            scene_display_name="Scene A",
            unity_scene_path="Assets/A.unity",
            status="running",
        )
    )
    db.commit()

    service = UnityBatchService(db)
    terminated: list[int] = []
    monkeypatch.setattr(service.runner, "_terminate_process", lambda pid, *_args, **_kwargs: terminated.append(pid))
    monkeypatch.setattr(service.runner, "_append_runner_log", lambda *_args, **_kwargs: None)

    service.stop_batch(batch.id)

    stop_file = tmp_path / "Library" / "XRDataCollector" / f"stop-task-{parent_task.id}"
    command_file = tmp_path / "Library" / "XRDataCollector" / f"orchestration-command-{batch.id}.json"
    assert stop_file.exists()
    assert command_file.exists()
    assert terminated == []


def test_reconcile_active_batch_marks_missing_cold_start_process_failed(db, monkeypatch, tmp_path):
    project = Project(name="Reconcile project")
    db.add(project)
    db.flush()
    parent_task = TaskModel(
        name="Parent",
        task_type="unity_multi_scene_orchestration",
        status="running",
        project_id=project.id,
        config={"launch_mode": "new_editor", "process_id": 999999},
    )
    db.add(parent_task)
    db.flush()
    project_path = str(tmp_path)
    batch = BatchModel(
        project_id=project.id,
        parent_task_id=parent_task.id,
        status="running",
        current_scene_index=0,
        scene_total=2,
        unity_project_path=project_path,
        unity_project_key=UnityProjectLeaseService.project_key(project_path),
    )
    db.add(batch)
    db.flush()
    db.add_all(
        [
            BatchItemModel(
                batch_id=batch.id,
                scene_index=0,
                scene_resource_id="scene-a",
                scene_display_name="Scene A",
                unity_scene_path="Assets/A.unity",
                status="running",
            ),
            BatchItemModel(
                batch_id=batch.id,
                scene_index=1,
                scene_resource_id="scene-b",
                scene_display_name="Scene B",
                unity_scene_path="Assets/B.unity",
                status="pending",
            ),
        ]
    )
    db.add(
        UnityProjectLease(
            project_key=batch.unity_project_key,
            project_path=project_path,
            owner_type="multi_scene",
            owner_id=batch.id,
            parent_task_id=parent_task.id,
            heartbeat_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
    )
    db.commit()

    monkeypatch.setattr("app.services.unity_runner_service.UnityRunnerService._process_exists", lambda self, pid: False)
    result = UnityBatchService(db).reconcile_active_batches()

    db.refresh(batch)
    db.refresh(parent_task)
    assert result["failed_batches"] == 1
    assert batch.status == "failed"
    assert parent_task.status == "failed"
    assert [item.status for item in batch.items] == ["failed", "cancelled"]
    assert db.query(UnityProjectLease).count() == 0
