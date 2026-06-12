import pytest
from fastapi import HTTPException

from app.services.test_metric_catalog import BASIC_METRIC_IDS, QUALITY_METRIC_IDS, get_default_enabled_quality_metrics
from app.services.test_scope_service import TestScopeService


def test_builtin_default_includes_all_keys():
    scope = TestScopeService.get_builtin_default_scope()
    assert set(scope["basic_metrics"]) == set(BASIC_METRIC_IDS)
    assert set(scope["quality_metrics"]) == set(QUALITY_METRIC_IDS)
    assert all(scope["basic_metrics"].values())
    assert scope["quality_metrics"] == get_default_enabled_quality_metrics()


def test_parent_disabled_forces_children_off():
    scope = TestScopeService.normalize_scope(
        {
            "basic_metrics": {key: True for key in BASIC_METRIC_IDS},
            "quality_categories": {"lighting": False, "materials": True, "post_processing": True, "physics": True},
            "quality_metrics": {key: True for key in QUALITY_METRIC_IDS},
        }
    )
    lighting_children = [key for key in QUALITY_METRIC_IDS if key.startswith("lighting.")]
    assert all(not scope["quality_metrics"][key] for key in lighting_children)


def test_empty_leaf_selection_is_rejected():
    scope = TestScopeService.normalize_scope(
        {
            "basic_metrics": {key: False for key in BASIC_METRIC_IDS},
            "quality_categories": {key: False for key in ("lighting", "materials", "post_processing", "physics")},
            "quality_metrics": {key: False for key in QUALITY_METRIC_IDS},
        }
    )
    with pytest.raises(HTTPException):
        TestScopeService.validate_scope(scope)


def test_draw_calls_enables_rendering_stats_collector():
    scope = TestScopeService.normalize_scope(
        {
            "basic_metrics": {key: (key == "frame_rate") for key in BASIC_METRIC_IDS},
            "quality_categories": {"lighting": False, "materials": True, "post_processing": False, "physics": False},
            "quality_metrics": {key: (key == "materials.draw_calls") for key in QUALITY_METRIC_IDS},
        }
    )
    plan = TestScopeService.resolve_execution_plan(scope)
    assert plan["collector_flags"]["rendering_stats"] is True
    assert plan["collector_flags"]["gpu"] is False
    assert "frame_time" in plan["support_metric_ids"] or "gpu" not in plan["support_metric_ids"]


def test_legacy_session_inferred_without_global_default():
    scope = TestScopeService.infer_scope_from_session_config(
        {
            "metric_checks": {"frame_rate": True, "frame_time": False, "cpu": True, "gpu": True, "memory": True, "device_info": True},
            "quality_checks": {"lighting": False, "materials": True, "post_processing": True, "physics": True},
        }
    )
    assert scope["basic_metrics"]["frame_time"] is False
    assert scope["quality_categories"]["lighting"] is False
    assert scope["source"] == "legacy_inferred"


def test_update_unity_settings_preserves_test_metrics(client, admin_auth_headers, tmp_path, monkeypatch):
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))
    service = system_settings_service.SystemSettingsService()
    service.update_default_test_scope(
        {
            "basic_metrics": {key: (key == "frame_rate") for key in BASIC_METRIC_IDS},
            "quality_categories": {"lighting": True, "materials": False, "post_processing": False, "physics": False},
            "quality_metrics": {key: key.startswith("lighting.") for key in QUALITY_METRIC_IDS},
        }
    )

    response = client.put(
        "/api/v1/system-settings/unity",
        headers=admin_auth_headers,
        json={
            "unity_executable_path": "/tmp/Unity",
            "unity_project_path": "/tmp/project",
            "collector_package_path": "",
        },
    )
    assert response.status_code == 200
    metrics = service.get_default_test_scope()["default_scope"]
    assert metrics["basic_metrics"]["frame_rate"] is True
    assert metrics["quality_categories"]["materials"] is False
