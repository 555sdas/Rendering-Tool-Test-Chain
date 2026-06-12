from app.services.unity_runner_service import UnityRunnerService


def test_admin_can_update_unity_settings(client, admin_auth_headers, tmp_path, monkeypatch):
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    unity_executable = tmp_path / "Unity"
    unity_executable.write_text("", encoding="utf-8")
    project_path = tmp_path / "DemoProject"
    scene_path = project_path / "Assets" / "Scenes" / "Demo.unity"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_text("", encoding="utf-8")
    collector_path = tmp_path / "unity-xr-collector"
    collector_path.mkdir()

    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))

    response = client.put(
        "/api/v1/system-settings/unity",
        headers=admin_auth_headers,
        json={
            "unity_executable_path": str(unity_executable),
            "unity_project_path": str(project_path),
            "collector_package_path": str(collector_path),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"]["unity_executable_exists"] is True
    assert data["status"]["unity_project_exists"] is True
    assert data["status"]["unity_scene_exists"] is True
    assert data["status"]["discovered_scene_count"] == 1
    assert data["status"]["discovered_scenes"] == ["Assets/Scenes/Demo.unity"]
    assert data["status"]["collector_package_exists"] is True
    assert settings_path.exists()


def test_unity_runner_lists_resources_from_system_settings(db, tmp_path, monkeypatch):
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    project_path = tmp_path / "DemoProject"
    scene_path = project_path / "Assets" / "Scenes" / "Demo.unity"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))
    system_settings_service.SystemSettingsService().update_unity_settings(
        {
            "unity_executable_path": str(tmp_path / "Unity"),
            "unity_project_path": str(project_path),
            "collector_package_path": "",
        }
    )

    service = UnityRunnerService(db)

    assert service.list_engines()[0]["id"] == "system-settings-engine"
    scenes = service.list_scenes()
    assert len(scenes) == 1
    assert scenes[0]["scene_path"] == "Assets/Scenes/Demo.unity"
    assert scenes[0]["id"].startswith("system-settings-scene-")
    assert scenes[0]["is_default"] is True


def test_discover_multiple_unity_scenes(db, tmp_path, monkeypatch):
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    project_path = tmp_path / "DemoProject"
    for relative in ["Assets/Scenes/A.unity", "Assets/Levels/B.unity"]:
        scene_file = project_path / relative
        scene_file.parent.mkdir(parents=True, exist_ok=True)
        scene_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))
    service = system_settings_service.SystemSettingsService()
    service.update_unity_settings(
        {
            "unity_executable_path": str(tmp_path / "Unity"),
            "unity_project_path": str(project_path),
            "collector_package_path": "",
        }
    )

    discovered = service.discover_unity_scenes(str(project_path))
    resources = service.get_unity_scene_resources()

    assert discovered == ["Assets/Levels/B.unity", "Assets/Scenes/A.unity"]
    assert len(resources) == 2
    assert {item["scene_path"] for item in resources} == set(discovered)
    assert resources[0]["is_default"] is True
    assert resources[1]["is_default"] is False


def test_default_unity_scene_is_marked_in_resources(db, tmp_path, monkeypatch):
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    project_path = tmp_path / "DemoProject"
    for relative in ["Assets/Scenes/A.unity", "Assets/Levels/B.unity"]:
        scene_file = project_path / relative
        scene_file.parent.mkdir(parents=True, exist_ok=True)
        scene_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))
    service = system_settings_service.SystemSettingsService()
    service.update_unity_settings(
        {
            "unity_executable_path": str(tmp_path / "Unity"),
            "unity_project_path": str(project_path),
            "unity_scene_path": "Assets/Scenes/A.unity",
            "collector_package_path": "",
        }
    )

    resources = service.get_unity_scene_resources()
    default_scenes = [item for item in resources if item["is_default"]]

    assert len(default_scenes) == 1
    assert default_scenes[0]["scene_path"] == "Assets/Scenes/A.unity"

    runner = UnityRunnerService(db)
    listed = runner.list_scenes()
    listed_default = [item for item in listed if item["is_default"]]
    assert len(listed_default) == 1
    assert listed_default[0]["scene_path"] == "Assets/Scenes/A.unity"


def test_non_admin_cannot_read_unity_settings(client, auth_headers):
    response = client.get("/api/v1/system-settings/unity", headers=auth_headers)
    assert response.status_code == 403


def test_unity_process_environment_is_minimal_utf8(db, monkeypatch):
    monkeypatch.setenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "桌面进程")
    environment = UnityRunnerService(db)._unity_process_environment()

    assert "CODEX_INTERNAL_ORIGINATOR_OVERRIDE" not in environment
    assert environment["LANG"] == "en_US.UTF-8"
    assert environment["LC_ALL"] == "en_US.UTF-8"


def test_unity_fatal_log_marks_task_and_session_failed(db):
    from datetime import datetime
    from app.models.test_session import TestSession, TestSessionStatus
    from app.models.test_task import TestTask, TestTaskStatus

    session = TestSession(name="#1", status=TestSessionStatus.RUNNING.value, started_at=datetime.utcnow())
    task = TestTask(
        name="Unity test",
        status=TestTaskStatus.RUNNING.value,
        task_type="unity_local_render_test",
        started_at=datetime.utcnow(),
    )
    db.add_all([session, task])
    db.commit()

    service = UnityRunnerService(db)
    service._sync_failed_task_from_logs(
        task,
        session,
        ["executeMethod class 'XRBatchTestRunner' could not be found."],
        None,
    )

    assert task.status == TestTaskStatus.FAILED.value
    assert session.status == TestSessionStatus.FAILED.value
    assert "自动化入口" in task.error_message


def test_open_project_task_is_dispatched_to_existing_editor(db, tmp_path):
    import fcntl
    import json

    project_path = tmp_path / "DemoProject"
    (project_path / "Temp").mkdir(parents=True)
    lock_path = project_path / "Temp" / "UnityLockfile"
    lock_file = lock_path.open("w")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    task_config_path = tmp_path / "task.json"
    task_config_path.write_text('{"quitOnComplete": true}', encoding="utf-8")

    try:
        process = UnityRunnerService(db)._launch_unity(
            engine={"executable_path": str(tmp_path / "Unity")},
            scene={"project_path": str(project_path)},
            task_config_path=task_config_path,
            log_path=tmp_path / "unity.log",
            batchmode=False,
        )
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()

    inbox = project_path / "Library" / "XRDataCollector" / "pending-task.json"
    assert process is None
    assert json.loads(task_config_path.read_text(encoding="utf-8"))["quitOnComplete"] is False
    assert json.loads(inbox.read_text(encoding="utf-8"))["configPath"] == str(task_config_path)


def test_existing_editor_refreshes_stale_collector_before_dispatch(db, tmp_path, monkeypatch):
    import os
    import time as stdlib_time

    project_path = tmp_path / "DemoProject"
    package_path = tmp_path / "unity-xr-collector"
    source = package_path / "Runtime" / "Collector.cs"
    source.parent.mkdir(parents=True)
    source.write_text("class Collector {}", encoding="utf-8")

    script_assemblies = project_path / "Library" / "ScriptAssemblies"
    script_assemblies.mkdir(parents=True)
    runtime_assembly = script_assemblies / "XRDataCollector.Runtime.dll"
    editor_assembly = script_assemblies / "XRDataCollector.Editor.dll"
    runtime_assembly.write_text("old", encoding="utf-8")
    editor_assembly.write_text("old", encoding="utf-8")
    stale_at = source.stat().st_mtime - 10
    os.utime(runtime_assembly, (stale_at, stale_at))
    os.utime(editor_assembly, (stale_at, stale_at))

    service = UnityRunnerService(db)

    def compile_after_marker(_seconds):
        compiled_at = stdlib_time.time() + 10
        os.utime(runtime_assembly, (compiled_at, compiled_at))
        os.utime(editor_assembly, (compiled_at, compiled_at))

    monkeypatch.setattr("app.services.unity_runner_service.time.sleep", compile_after_marker)
    service._ensure_existing_editor_plugin_current(
        {
            "project_path": str(project_path),
            "collector_package_path": str(package_path),
        },
        None,
        timeout_seconds=2,
    )

    marker = project_path / "Assets" / "XRDataCollectorGenerated" / "Editor" / "PackageRefreshMarker.cs"
    assert marker.exists()
    assert "SourceTimestamp" in marker.read_text(encoding="utf-8")


def test_unity_progress_requires_device_token_and_is_cached(client, db, admin_auth_headers):
    from app.config import get_settings
    from app.models.test_task import TestTask

    task = TestTask(name="Realtime task", task_type="unity_local_render_test")
    db.add(task)
    db.commit()

    payload = {
        "task_id": task.id,
        "session_id": 42,
        "phase": "frame_rate",
        "phase_label": "帧率采集",
        "progress": 0.25,
        "remaining_seconds": 15,
        "sample_count": 3,
        "fps": 72,
        "frame_time_ms": 13.8,
        "cpu_usage_percent": 20,
        "gpu_usage_percent": 30,
        "memory_mb": 512,
        "draw_calls": 100,
    }

    denied = client.post(f"/api/v1/unity-runner/progress/{task.id}", json=payload)
    accepted = client.post(
        f"/api/v1/unity-runner/progress/{task.id}",
        headers={"X-Device-Token": get_settings().DEVICE_TOKEN},
        json=payload,
    )
    latest = client.get(
        f"/api/v1/unity-runner/progress/{task.id}/latest",
        headers=admin_auth_headers,
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert latest.status_code == 200
    assert latest.json()["item"]["fps"] == 72


def test_missing_unity_process_marks_residual_task_failed(db, monkeypatch):
    from datetime import datetime, timezone
    from app.models.test_session import TestSession, TestSessionStatus
    from app.models.test_task import TestTask, TestTaskStatus

    session = TestSession(name="#1", status=TestSessionStatus.RUNNING.value, started_at=datetime.utcnow())
    task = TestTask(
        name="Residual Unity test",
        status=TestTaskStatus.RUNNING.value,
        task_type="unity_local_render_test",
        started_at=datetime.utcnow(),
        config={"process_id": 999999, "platform_session_id": 1, "launch_mode": "new_editor"},
    )
    db.add_all([session, task])
    db.commit()
    monkeypatch.setattr(UnityRunnerService, "_process_exists", lambda self, pid: False)

    task.started_at = datetime.now(timezone.utc)
    session.started_at = datetime.now(timezone.utc)
    UnityRunnerService(db)._sync_stale_task(task, session)

    assert task.status == TestTaskStatus.FAILED.value
    assert session.status == TestSessionStatus.FAILED.value
    assert "进程已不存在" in task.error_message
