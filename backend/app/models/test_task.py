import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class TestTaskStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestTask(Base):
    __tablename__ = "test_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TestTaskStatus] = mapped_column(String(20), default=TestTaskStatus.PENDING.value)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"))
    scene_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scene_assets.id"))
    creator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    config: Mapped[dict | None] = mapped_column(JSON)
    target_devices: Mapped[list | None] = mapped_column(JSON)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    result_summary: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    creator: Mapped["User"] = relationship("User", back_populates="test_tasks")
    project: Mapped["Project"] = relationship("Project", back_populates="test_tasks")
    scene: Mapped["SceneAsset"] = relationship("SceneAsset", back_populates="test_tasks")
