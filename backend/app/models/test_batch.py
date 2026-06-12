import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class TestBatchStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_USER_DECISION = "awaiting_user_decision"
    COMPLETED = "completed"
    PARTIAL_COMPLETED = "partial_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestBatch(Base):
    __tablename__ = "test_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), index=True)
    creator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    parent_task_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_tasks.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default=TestBatchStatus.PENDING.value, index=True)
    current_scene_index: Mapped[int] = mapped_column(Integer, default=0)
    scene_total: Mapped[int] = mapped_column(Integer, default=0)
    unity_project_path: Mapped[str] = mapped_column(String(1024))
    unity_project_key: Mapped[str] = mapped_column(String(64), index=True)
    config: Mapped[dict | None] = mapped_column(JSON)
    result_summary: Mapped[dict | None] = mapped_column(JSON)
    decision_version: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    items: Mapped[list["TestBatchItem"]] = relationship(
        "TestBatchItem",
        back_populates="batch",
        order_by="TestBatchItem.scene_index",
    )


class TestBatchItemStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_USER_DECISION = "awaiting_user_decision"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TestBatchItem(Base):
    __tablename__ = "test_batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_batches.id"), index=True)
    scene_index: Mapped[int] = mapped_column(Integer)
    scene_resource_id: Mapped[str] = mapped_column(String(200))
    scene_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scene_assets.id"))
    scene_display_name: Mapped[str] = mapped_column(String(200))
    unity_scene_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default=TestBatchItemStatus.PENDING.value, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    current_task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("test_tasks.id"))
    current_session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("test_sessions.id"))
    config: Mapped[dict | None] = mapped_column(JSON)
    attempt_history: Mapped[list | None] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    batch: Mapped["TestBatch"] = relationship("TestBatch", back_populates="items")
