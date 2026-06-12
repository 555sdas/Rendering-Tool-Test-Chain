import json
from datetime import datetime

import pytest

from app.models.performance_sample import PerformanceSample
from app.models.test_session import TestSession as SessionModel
from app.models.test_session import TestSessionStatus as SessionStatus
from app.services.render_quality_service import RenderQualityService
from app.services.scoring_definition_service import (
    ScoringDefinitionService,
    ScoringDefinitionValidationError,
)
from app.services.system_settings_service import SystemSettingsService
from app.services.test_scope_service import TestScopeService


def test_builtin_definition_is_25_each():
    definition = ScoringDefinitionService.get_builtin_definition()
    assert definition["category_weights"] == {
        "lighting": 25.0,
        "material": 25.0,
        "post_processing": 25.0,
        "physics": 25.0,
    }


def test_validate_rejects_invalid_totals():
    with pytest.raises(ScoringDefinitionValidationError):
        ScoringDefinitionService.validate_definition(
            {
                "schema_version": 1,
                "category_weights": {
                    "lighting": 40,
                    "material": 30,
                    "post_processing": 20,
                    "physics": 5,
                },
            }
        )


def test_validate_rejects_missing_and_unknown_categories():
    with pytest.raises(ScoringDefinitionValidationError):
        ScoringDefinitionService.validate_definition(
            {"schema_version": 1, "category_weights": {"lighting": 100}}
        )
    with pytest.raises(ScoringDefinitionValidationError):
        ScoringDefinitionService.validate_definition(
            {
                "schema_version": 1,
                "category_weights": {
                    "lighting": 25,
                    "material": 25,
                    "post_processing": 25,
                    "physics": 25,
                    "unknown": 1,
                },
            }
        )


def test_validate_rejects_non_numeric_and_out_of_range():
    with pytest.raises(ScoringDefinitionValidationError):
        ScoringDefinitionService.validate_definition(
            {
                "schema_version": 1,
                "category_weights": {
                    "lighting": "25",
                    "material": 25,
                    "post_processing": 25,
                    "physics": 25,
                },
            }
        )
    with pytest.raises(ScoringDefinitionValidationError):
        ScoringDefinitionService.validate_definition(
            {
                "schema_version": 1,
                "category_weights": {
                    "lighting": -1,
                    "material": 25,
                    "post_processing": 25,
                    "physics": 51,
                },
            }
        )


def test_scoring_definition_api_save_reset_and_audit(client, admin_auth_headers, tmp_path, monkeypatch, db):
    from app.models.audit_log import AuditLog
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "unity": {"unity_executable_path": "/tmp/Unity"},
                "test_metrics": {"default_scope": TestScopeService.get_builtin_default_scope()},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))

    custom = {
        "schema_version": 1,
        "category_weights": {
            "lighting": 40,
            "material": 30,
            "post_processing": 20,
            "physics": 10,
        },
    }
    save_response = client.put(
        "/api/v1/system-settings/scoring-definition",
        headers=admin_auth_headers,
        json=custom,
    )
    assert save_response.status_code == 200
    assert save_response.json()["definition"]["category_weights"]["lighting"] == 40

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    assert stored["unity"]["unity_executable_path"] == "/tmp/Unity"
    assert stored["test_metrics"]["default_scope"]["schema_version"] == 1

    reset_response = client.post(
        "/api/v1/system-settings/scoring-definition/reset",
        headers=admin_auth_headers,
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["summary"]["is_default"] is True

    audits = db.query(AuditLog).filter(AuditLog.resource_type == "scoring_definition").all()
    assert len(audits) >= 2


def test_resolve_session_definition_prefers_snapshot_and_falls_back():
    snapshot = {
        "schema_version": 1,
        "category_weights": {
            "lighting": 40,
            "material": 30,
            "post_processing": 20,
            "physics": 10,
        },
    }
    resolved = ScoringDefinitionService.resolve_session_definition({"scoring_definition": snapshot})
    assert resolved["source"] == "session_snapshot"
    assert resolved["definition"]["category_weights"]["lighting"] == 40

    legacy = ScoringDefinitionService.resolve_session_definition({})
    assert legacy["source"] == "builtin_default"

    broken = ScoringDefinitionService.resolve_session_definition({"scoring_definition": {"category_weights": {}}})
    assert broken["source"] == "builtin_default_fallback"


def test_new_session_snapshot_uses_global_definition(client, admin_auth_headers, tmp_path, monkeypatch, db):
    from app.services import system_settings_service

    settings_path = tmp_path / "system_settings.json"
    monkeypatch.setattr(system_settings_service.settings, "SYSTEM_SETTINGS_PATH", str(settings_path))
    SystemSettingsService().update_scoring_definition(
        {
            "schema_version": 1,
            "category_weights": {
                "lighting": 40,
                "material": 30,
                "post_processing": 20,
                "physics": 10,
            },
        }
    )

    response = client.post(
        "/api/v1/data-collection/test-sessions",
        headers=admin_auth_headers,
        json={"name": "#scoring-snapshot"},
    )
    assert response.status_code == 200
    session = db.query(SessionModel).filter(SessionModel.name == "#scoring-snapshot").one()
    assert session.config["scoring_definition"]["category_weights"]["lighting"] == 40


def test_custom_weights_change_overall_score(db):
    scope = TestScopeService.get_builtin_default_scope()
    session = SessionModel(
        name="#custom-score",
        status=SessionStatus.COMPLETED.value,
        started_at=datetime.utcnow(),
        config={
            "test_scope": scope,
            "scoring_definition": {
                "schema_version": 1,
                "category_weights": {
                    "lighting": 40,
                    "material": 30,
                    "post_processing": 20,
                    "physics": 10,
                },
            },
        },
    )
    db.add(session)
    db.commit()

    db.add(
        PerformanceSample(
            test_session_id=session.id,
            timestamp=datetime.utcnow(),
            fps=60,
            extra_metrics={"render_quality": {"active_light_count": 8}},
        )
    )
    db.commit()

    result = RenderQualityService(db).evaluate_session(session.id)
    assert result["scoring_definition_source"] == "session_snapshot"
    assert result["score_formula"]["effective_total_weight"] == 100
    assert result["scoring_definition"]["category_weights"]["lighting"] == 40
    lighting = next(item for item in result["categories"] if item["key"] == "lighting")
    assert lighting["weight"] == 40


def test_zero_weight_category_excluded_from_overall_score(db):
    scope = TestScopeService.get_builtin_default_scope()
    session = SessionModel(
        name="#zero-weight",
        status=SessionStatus.COMPLETED.value,
        started_at=datetime.utcnow(),
        config={
            "test_scope": scope,
            "scoring_definition": {
                "schema_version": 1,
                "category_weights": {
                    "lighting": 50,
                    "material": 50,
                    "post_processing": 0,
                    "physics": 0,
                },
            },
        },
    )
    db.add(session)
    db.commit()
    db.add(
        PerformanceSample(
            test_session_id=session.id,
            timestamp=datetime.utcnow(),
            fps=60,
            extra_metrics={"render_quality": {"active_light_count": 8}},
        )
    )
    db.commit()

    result = RenderQualityService(db).evaluate_session(session.id)
    post = next(item for item in result["categories"] if item["key"] == "post_processing")
    assert post["included_in_overall_score"] is False
    assert "post_processing" not in result["score_formula"]["included_categories"]


def test_all_zero_weights_for_tested_categories_yield_null_overall(db):
    scope = TestScopeService.normalize_scope(
        {
            "basic_metrics": {key: True for key in TestScopeService.get_builtin_default_scope()["basic_metrics"]},
            "quality_categories": {"lighting": True, "materials": True, "post_processing": False, "physics": False},
            "quality_metrics": {key: key.startswith("lighting.") or key.startswith("materials.") for key in TestScopeService.get_builtin_default_scope()["quality_metrics"]},
        }
    )
    session = SessionModel(
        name="#all-zero-tested",
        status=SessionStatus.COMPLETED.value,
        started_at=datetime.utcnow(),
        config={
            "test_scope": scope,
            "scoring_definition": {
                "schema_version": 1,
                "category_weights": {
                    "lighting": 0,
                    "material": 0,
                    "post_processing": 50,
                    "physics": 50,
                },
            },
        },
    )
    db.add(session)
    db.commit()
    db.add(
        PerformanceSample(
            test_session_id=session.id,
            timestamp=datetime.utcnow(),
            fps=60,
            extra_metrics={"render_quality": {"active_light_count": 8, "material_count": 12}},
        )
    )
    db.commit()

    result = RenderQualityService(db).evaluate_session(session.id)
    assert result["overall_score"] is None
    assert result["overall_score_reason"] == "所有参与测试分类的配置权重均为 0，无法计算总分"
