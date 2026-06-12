from datetime import datetime

from app.models.performance_sample import PerformanceSample
from app.models.test_session import TestSession as SessionModel
from app.models.test_session import TestSessionStatus as SessionStatus
from app.services.quality_metric_status_service import (
    build_all_metric_status,
    build_metric_status_entry,
    compute_data_completeness,
    confidence_grade_from_completeness,
    summarize_coverage,
)
from app.services.render_quality_service import RenderQualityService
from app.services.test_scope_service import TestScopeService


def _scope_with_all_quality_enabled():
    scope = TestScopeService.get_builtin_default_scope()
    scope["quality_metrics"] = {key: True for key in scope["quality_metrics"]}
    return scope


def test_skipped_when_metric_not_selected():
    scope = TestScopeService.normalize_scope(
        {
            "basic_metrics": {key: True for key in TestScopeService.get_builtin_default_scope()["basic_metrics"]},
            "quality_categories": {"lighting": True, "materials": False, "post_processing": False, "physics": False},
            "quality_metrics": {key: key == "lighting.active_lights" for key in _scope_with_all_quality_enabled()["quality_metrics"]},
        }
    )
    entry = build_metric_status_entry("materials.texture_memory", scope, {})
    assert entry["status"] == "skipped"
    assert entry["reason_code"] == "not_selected"


def test_manifest_available_with_stats():
    scope = _scope_with_all_quality_enabled()
    manifest = [{"id": "lighting.active_lights", "status": "available", "validSampleCount": 3}]
    stats = {"peak_active_light_count": 12}
    entry = build_metric_status_entry("lighting.active_lights", scope, stats, manifest=manifest)
    assert entry["status"] == "available"
    assert entry["inferred"] is False


def test_planned_metric_unavailable_without_manifest():
    scope = _scope_with_all_quality_enabled()
    entry = build_metric_status_entry("lighting.exposure_artifacts", scope, {})
    assert entry["status"] == "unavailable"
    assert entry["inferred"] is True


def test_manifest_available_but_stats_missing_becomes_missing():
    scope = _scope_with_all_quality_enabled()
    manifest = [{"id": "materials.texture_memory", "status": "available", "validSampleCount": 2}]
    entry = build_metric_status_entry("materials.texture_memory", scope, {}, manifest=manifest)
    assert entry["status"] == "missing"
    assert entry["reason_code"] == "no_valid_samples"


def test_new_heuristic_metrics_are_available_with_manifest_and_stats():
    scope = _scope_with_all_quality_enabled()
    manifest = [
        {"id": "post_processing.warnings", "status": "available", "validSampleCount": 2},
        {"id": "physics.penetration", "status": "available", "validSampleCount": 2},
    ]
    stats = {
        "post_processing_warning_count": 1,
        "peak_penetration_event_count": 3,
    }

    warning = build_metric_status_entry("post_processing.warnings", scope, stats, manifest=manifest)
    penetration = build_metric_status_entry("physics.penetration", scope, stats, manifest=manifest)

    assert warning["status"] == "available"
    assert penetration["status"] == "available"


def test_coverage_and_completeness():
    scope = _scope_with_all_quality_enabled()
    stats = {
        "peak_active_light_count": 5,
        "peak_shadow_caster_count": 2,
        "peak_material_count": 10,
        "avg_draw_calls": 120,
        "peak_texture_memory_mb": 512,
    }
    manifest = [
        {"id": "lighting.active_lights", "status": "available", "validSampleCount": 1},
        {"id": "lighting.exposure_artifacts", "status": "unavailable", "reasonCode": "not_implemented"},
    ]
    all_status = build_all_metric_status(scope, stats, manifest=manifest)
    coverage = summarize_coverage(all_status, scope)
    assert coverage["selected"] > 0
    assert coverage["skipped"] >= 0
    completeness = compute_data_completeness(coverage)
    assert completeness is not None
    assert 0 <= completeness <= 1
    assert confidence_grade_from_completeness(completeness) in {"A", "B", "C", "D"}


def test_render_quality_service_returns_metric_status(db):
    session = SessionModel(
        name="#quality-status",
        status=SessionStatus.COMPLETED.value,
        started_at=datetime.utcnow(),
        config={
            "test_scope": TestScopeService.get_builtin_default_scope(),
            "quality_metric_manifest": [
                {"id": "lighting.active_lights", "status": "available", "validSampleCount": 1},
                {"id": "post_processing.warnings", "status": "available", "validSampleCount": 1},
                {"id": "physics.penetration", "status": "available", "validSampleCount": 1},
            ],
        },
    )
    db.add(session)
    db.commit()

    db.add(
        PerformanceSample(
            test_session_id=session.id,
            timestamp=datetime.utcnow(),
            fps=60,
            extra_metrics={
                "render_quality": {
                    "active_light_count": 8,
                    "post_processing_warning_count": 2,
                    "penetration_event_count": 1,
                }
            },
        )
    )
    db.commit()

    result = RenderQualityService(db).evaluate_session(session.id)
    assert "metric_status" in result
    assert result["metric_status"]["lighting.active_lights"]["status"] == "available"
    assert result["data_completeness"] is not None
    assert result["confidence_grade"] in {"A", "B", "C", "D", "未评估"}
    lighting = next(cat for cat in result["categories"] if cat["key"] == "lighting")
    assert "metric_status" in lighting
    assert lighting["metric_status"]["lighting.active_lights"]["status"] == "available"
    post_processing = next(cat for cat in result["categories"] if cat["key"] == "post_processing")
    physics = next(cat for cat in result["categories"] if cat["key"] == "physics")
    assert post_processing["metrics"]["post_processing_warning_count"] == 2
    assert post_processing["metric_status"]["post_processing.warnings"]["status"] == "available"
    assert physics["metrics"]["penetration_event_count"] == 1
    assert physics["metric_status"]["physics.penetration"]["status"] == "available"
