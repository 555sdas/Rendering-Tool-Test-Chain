from app.services.unity_runner_service import UnityRunnerService


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
