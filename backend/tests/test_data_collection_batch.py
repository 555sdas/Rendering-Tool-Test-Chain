from datetime import datetime, timedelta

from app.models.test_session import TestSession as SessionModel
from app.models.test_session import TestSessionStatus as SessionStatus
from app.models.performance_sample import PerformanceSample


def test_batch_upload_rejects_invalid_session_time_and_duration(client, db, admin_auth_headers):
    started_at = datetime.utcnow()
    session = SessionModel(
        name="#1",
        status=SessionStatus.RUNNING.value,
        started_at=started_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    first_sample = datetime.utcnow()
    response = client.post(
        f"/api/v1/data-collection/test-sessions/{session.id}/samples/batch",
        headers=admin_auth_headers,
        json={
            "session": {
                "startTime": "0001-01-01T00:00:00",
                "duration": 63916758234.125,
            },
            "samples": [
                {"timestamp": first_sample.isoformat(), "elapsedTime": 1, "frameRate": 60},
                {
                    "timestamp": (first_sample + timedelta(seconds=3)).isoformat(),
                    "elapsedTime": 4,
                    "frameRate": 59,
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert 3 <= data["duration_seconds"] <= 4


def test_batch_upload_preserves_zero_metrics_and_maps_graphics_memory(client, db, admin_auth_headers):
    session = SessionModel(name="#metrics", status=SessionStatus.RUNNING.value, started_at=datetime.utcnow())
    db.add(session)
    db.commit()

    response = client.post(
        f"/api/v1/data-collection/test-sessions/{session.id}/samples/batch",
        headers=admin_auth_headers,
        json={
            "samples": [{
                "timestamp": datetime.utcnow().isoformat(),
                "frameRate": 60,
                "cpuUsagePercent": 0,
                "gpuUsagePercent": 0,
                "drawCalls": 0,
                "triangles": 0,
                "vertices": 0,
                "totalMemoryMB": 256,
                "graphicsMemoryMB": 128,
                "deviceInfo": {"deviceModel": "Cold Start Mac"},
                "renderQuality": {"active_light_count": 0},
            }],
        },
    )

    assert response.status_code == 200
    sample = db.query(PerformanceSample).filter(PerformanceSample.test_session_id == session.id).one()
    assert sample.cpu_usage_percent == 0
    assert sample.gpu_usage_percent == 0
    assert sample.draw_calls == 0
    assert sample.texture_memory_mb == 128
    assert sample.extra_metrics["device_info"]["deviceModel"] == "Cold Start Mac"
    assert sample.extra_metrics["render_quality"]["active_light_count"] == 0
