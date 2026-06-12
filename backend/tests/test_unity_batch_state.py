from app.models.test_batch import TestBatchItemStatus, TestBatchStatus
from app.services.unity_batch_state import (
    compute_allowed_actions,
    compute_overall_progress,
    derive_batch_status_from_items,
    summarize_batch_items,
)


def test_compute_allowed_actions_awaiting_decision():
    assert compute_allowed_actions(TestBatchStatus.AWAITING_USER_DECISION.value) == [
        "retry",
        "skip",
        "abort",
    ]


def test_compute_allowed_actions_running():
    assert compute_allowed_actions(TestBatchStatus.RUNNING.value) == ["abort"]


def test_summarize_batch_items_counts():
    items = [
        {"status": TestBatchItemStatus.COMPLETED.value},
        {"status": TestBatchItemStatus.RUNNING.value},
        {"status": TestBatchItemStatus.SKIPPED.value},
    ]
    summary = summarize_batch_items(items)
    assert summary["scene_total"] == 3
    assert summary["completed_count"] == 1
    assert summary["running_count"] == 1
    assert summary["skipped_count"] == 1


def test_derive_batch_status_all_completed():
    items = [{"status": TestBatchItemStatus.COMPLETED.value}] * 2
    assert derive_batch_status_from_items(items) == TestBatchStatus.COMPLETED.value


def test_derive_batch_status_partial_completed():
    items = [
        {"status": TestBatchItemStatus.COMPLETED.value},
        {"status": TestBatchItemStatus.SKIPPED.value},
    ]
    assert derive_batch_status_from_items(items) == TestBatchStatus.PARTIAL_COMPLETED.value


def test_compute_overall_progress_weighted():
    items = [
        {"config": {"frame_rate_duration_seconds": 30, "metrics_duration_seconds": 30}},
        {"config": {"frame_rate_duration_seconds": 60, "metrics_duration_seconds": 60}},
    ]
    progress = compute_overall_progress(items, current_scene_index=1, current_scene_progress=0.5)
    assert 0.35 < progress < 0.75
