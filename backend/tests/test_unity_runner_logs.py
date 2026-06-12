import subprocess

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
