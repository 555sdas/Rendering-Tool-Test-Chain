import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class TestSessionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestSession(Base):
    __tablename__ = "test_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TestSessionStatus] = mapped_column(String(20), default=TestSessionStatus.PENDING.value)
    device_model: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(50))
    xr_runtime: Mapped[str | None] = mapped_column(String(50))
    app_version: Mapped[str | None] = mapped_column(String(50))
    scene_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scene_assets.id"))
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"))
    config: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="test_sessions")
    project: Mapped["Project"] = relationship("Project", back_populates="test_sessions")
    scene: Mapped["SceneAsset"] = relationship("SceneAsset", back_populates="test_sessions")
    performance_samples: Mapped[list["PerformanceSample"]] = relationship("PerformanceSample", back_populates="test_session")
