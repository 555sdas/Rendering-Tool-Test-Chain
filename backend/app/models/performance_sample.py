from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PerformanceSample(Base):
    __tablename__ = "performance_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_session_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_sessions.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frame_time_ms: Mapped[float | None] = mapped_column(Float)
    fps: Mapped[float | None] = mapped_column(Float)
    cpu_usage_percent: Mapped[float | None] = mapped_column(Float)
    gpu_usage_percent: Mapped[float | None] = mapped_column(Float)
    memory_mb: Mapped[float | None] = mapped_column(Float)
    battery_level: Mapped[float | None] = mapped_column(Float)
    battery_temperature: Mapped[float | None] = mapped_column(Float)
    draw_calls: Mapped[int | None] = mapped_column(Integer)
    triangle_count: Mapped[int | None] = mapped_column(Integer)
    vertex_count: Mapped[int | None] = mapped_column(Integer)
    set_pass_calls: Mapped[int | None] = mapped_column(Integer)
    texture_memory_mb: Mapped[float | None] = mapped_column(Float)
    mesh_memory_mb: Mapped[float | None] = mapped_column(Float)
    render_texture_memory_mb: Mapped[float | None] = mapped_column(Float)
    gc_collect_count: Mapped[int | None] = mapped_column(Integer)
    gc_allocated_mb: Mapped[float | None] = mapped_column(Float)
    screen_resolution: Mapped[str | None] = mapped_column(String(50))
    tracking_state: Mapped[str | None] = mapped_column(String(50))
    prediction_error_ms: Mapped[float | None] = mapped_column(Float)
    pose_latency_ms: Mapped[float | None] = mapped_column(Float)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON)

    test_session: Mapped["TestSession"] = relationship("TestSession", back_populates="performance_samples")
