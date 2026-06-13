import subprocess
from datetime import datetime

from app.models.project import Project
from app.models.test_batch import TestBatch as BatchModel, TestBatchItem as BatchItemModel
from app.models.test_session import TestSession as SessionModel
from app.models.test_task import TestTask as TaskModel
from app.services.unity_runner_service import UnityRunnerService


def test_scope_editor_log_to_task_uses_latest_task_anchor():
    service = UnityRunnerService(db=None)  # type: ignore[arg-type]
    lines = [
        "[XRBatchTestRunner] 任务 10 / 平台会话 100",
        "[XRTestManager] old task noise",
        "[XRBatchTestRunner] 任务 12 / 平台会话 200",
        "[XRTestManager] 阶段2已开始",
        "[TestDataUploader] 上传成功",
    ]
    scoped = service._scope_editor_log_to_task(lines, task_id=12, session_id=200)
    assert scoped[0].endswith("任务 12 / 平台会话 200")
    assert any("阶段2已开始" in line for line in scoped)
    assert not any("任务 10" in line for line in scoped)


def test_missing_unity_log_lines_for_existing_editor_is_not_waiting_message():
    service = UnityRunnerService(db=None)  # type: ignore[arg-type]
    lines = service._missing_unity_log_lines("existing_editor")
    assert any("热启动" in line for line in lines)
    assert not any("等待编辑器启动" in line for line in lines)


def test_missing_unity_log_lines_for_new_editor_keeps_waiting_message():
    service = UnityRunnerService(db=None)  # type: ignore[arg-type]
    lines = service._missing_unity_log_lines("new_editor")
    assert lines == ["Unity 日志尚未生成，等待编辑器启动。"]


def test_filter_unity_log_lines_prioritizes_plugin_messages():
    service = UnityRunnerService(db=None)  # type: ignore[arg-type]
    lines = [
        "[Licensing::Client] Successfully resolved entitlement details",
        "UnloadTime: 10.222292 ms",
        "[XRTestManager] 样本 #5 (frame_rate)：FPS=104.3, CPU=96.8%",
        "Some random engine noise",
        "NullReferenceException: something failed",
    ]
    filtered = service._filter_unity_log_lines(lines, limit=20)
    assert any("XRTestManager" in line for line in filtered)
    assert any("NullReferenceException" in line for line in filtered)
    assert not any("Licensing::Client" in line for line in filtered)


def test_completed_session_watchdog_terminates_unresponsive_unity(monkeypatch):
    service = UnityRunnerService(db=None)  # type: ignore[arg-type]
    service.UNITY_PROCESS_POLL_SECONDS = 0
    service.UNITY_COMPLETED_EXIT_GRACE_SECONDS = 10

    class HungUnityProcess:
        pid = 4321

        def __init__(self):
            self.wait_calls = 0

        def wait(self, timeout=None):
            self.wait_calls += 1
            if self.wait_calls <= 2:
                raise subprocess.TimeoutExpired("Unity", timeout)
            return -15

    process = HungUnityProcess()
    terminated: list[tuple[int, bool]] = []
    log_messages: list[str] = []
    monotonic_values = iter([100.0, 111.0])

    monkeypatch.setattr(
        service,
        "_terminate_process",
        lambda pid, _log_path, force=False: terminated.append((pid, force)),
    )
    monkeypatch.setattr(
        service,
        "_append_runner_log",
        lambda _path, _level, message: log_messages.append(message),
    )
    monkeypatch.setattr("app.services.unity_runner_service.time.monotonic", lambda: next(monotonic_values))

    return_code = service._wait_for_unity_process_exit(
        process=process,  # type: ignore[arg-type]
        session_completed=lambda: True,
        runner_log_path=None,
    )

    assert return_code == -15
    assert terminated == [(4321, False)]
    assert any("原生关闭流程" in message for message in log_messages)


def test_list_active_runs_returns_single_and_multi_scene_summaries(db):
    project = Project(name="Active runs")
    db.add(project)
    db.flush()
    single_session = SessionModel(
        name="#single",
        status="running",
        project_id=project.id,
        config={},
        started_at=datetime.utcnow(),
    )
    db.add(single_session)
    db.flush()
    single_task = TaskModel(
        name="Single",
        task_type="unity_local_render_test",
        status="running",
        project_id=project.id,
        started_at=datetime.utcnow(),
        config={
            "platform_session_id": single_session.id,
            "scene_resource_name": "Garden",
        },
        result_summary={"latest_progress": {"progress": 0.4, "phase_label": "采集帧率", "remaining_seconds": 12}},
    )
    parent_task = TaskModel(
        name="Multi",
        task_type="unity_multi_scene_orchestration",
        status="running",
        project_id=project.id,
        started_at=datetime.utcnow(),
        config={"run_mode": "multi_scene"},
    )
    db.add_all([single_task, parent_task])
    db.flush()
    batch = BatchModel(
        project_id=project.id,
        parent_task_id=parent_task.id,
        status="running",
        current_scene_index=1,
        scene_total=2,
        unity_project_path="/tmp/active-runs",
        unity_project_key="active-runs",
        started_at=datetime.utcnow(),
        result_summary={"overall_progress": 0.75, "latest_progress": {"phase_label": "采集指标"}},
    )
    db.add(batch)
    db.flush()
    db.add(
        BatchItemModel(
            batch_id=batch.id,
            scene_index=1,
            scene_resource_id="scene-b",
            scene_display_name="Scene B",
            unity_scene_path="Assets/B.unity",
            status="running",
        )
    )
    db.commit()

    rows = UnityRunnerService(db).list_active_runs()

    assert {row["run_mode"] for row in rows} == {"single_scene", "multi_scene"}
    single = next(row for row in rows if row["run_mode"] == "single_scene")
    multi = next(row for row in rows if row["run_mode"] == "multi_scene")
    assert single["scene_name"] == "Garden"
    assert single["progress"] == 0.4
    assert multi["scene_name"] == "Scene B"
    assert multi["progress"] == 0.75


def test_active_runs_api_requires_view_permission_and_returns_items(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.routers.unity_runner.UnityRunnerService.list_active_runs",
        lambda self: [{"task_id": 7, "project_id": 1, "run_mode": "single_scene"}],
    )

    response = client.get("/api/v1/unity-runner/active-runs", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["task_id"] == 7
