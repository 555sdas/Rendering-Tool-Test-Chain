"""多场景批次状态机纯函数。"""

from __future__ import annotations

from typing import Any

from app.models.test_batch import TestBatchItemStatus, TestBatchStatus


TERMINAL_BATCH_STATUSES = {
    TestBatchStatus.COMPLETED.value,
    TestBatchStatus.PARTIAL_COMPLETED.value,
    TestBatchStatus.FAILED.value,
    TestBatchStatus.CANCELLED.value,
}


def compute_allowed_actions(batch_status: str, item_status: str | None = None) -> list[str]:
    if batch_status == TestBatchStatus.AWAITING_USER_DECISION.value:
        return ["retry", "skip", "abort"]
    if batch_status in {TestBatchStatus.RUNNING.value, TestBatchStatus.PENDING.value}:
        return ["abort"]
    return []


def summarize_batch_items(items: list[Any]) -> dict[str, Any]:
    counts = {
        "scene_total": len(items),
        "completed_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
    }
    for item in items:
        status = getattr(item, "status", None) or (item.get("status") if isinstance(item, dict) else None)
        if status == TestBatchItemStatus.COMPLETED.value:
            counts["completed_count"] += 1
        elif status == TestBatchItemStatus.FAILED.value:
            counts["failed_count"] += 1
        elif status == TestBatchItemStatus.SKIPPED.value:
            counts["skipped_count"] += 1
        elif status == TestBatchItemStatus.CANCELLED.value:
            counts["cancelled_count"] += 1
        elif status in {
            TestBatchItemStatus.RUNNING.value,
            TestBatchItemStatus.UPLOADING.value,
            TestBatchItemStatus.AWAITING_USER_DECISION.value,
        }:
            counts["running_count"] += 1
    return counts


def derive_batch_status_from_items(items: list[Any], *, forced: str | None = None) -> str:
    if forced:
        return forced
    summary = summarize_batch_items(items)
    total = summary["scene_total"]
    if total == 0:
        return TestBatchStatus.FAILED.value
    if summary["completed_count"] == total:
        return TestBatchStatus.COMPLETED.value
    if summary["completed_count"] > 0 and summary["failed_count"] + summary["skipped_count"] > 0:
        if summary["running_count"] == 0:
            return TestBatchStatus.PARTIAL_COMPLETED.value
    if summary["failed_count"] > 0 and summary["running_count"] == 0 and summary["completed_count"] == 0:
        return TestBatchStatus.FAILED.value
    return TestBatchStatus.RUNNING.value


def compute_overall_progress(
    items: list[dict[str, Any]],
    *,
    current_scene_index: int,
    current_scene_progress: float,
) -> float:
    weights: list[float] = []
    for item in items:
        cfg = item.get("config") or {}
        weight = float(cfg.get("frame_rate_duration_seconds") or 30) + float(
            cfg.get("metrics_duration_seconds") or 30
        ) + 90.0
        weights.append(max(weight, 1.0))
    total_weight = sum(weights) or 1.0
    completed_weight = sum(weights[:current_scene_index])
    current_weight = weights[current_scene_index] if current_scene_index < len(weights) else 0.0
    return min(1.0, max(0.0, (completed_weight + current_weight * current_scene_progress) / total_weight))
