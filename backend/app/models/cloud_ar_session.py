import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class CloudARSessionStatus(str, enum.Enum):
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    ACTIVE = "active"
    STREAMING = "streaming"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CLOSED = "closed"


class CloudARSession(Base):
    __tablename__ = "cloud_ar_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CloudARSessionStatus] = mapped_column(String(20), default=CloudARSessionStatus.INITIALIZING.value)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    project_id: Mapped[int | None] = mapped_column(Integer)
    scene_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scene_assets.id"))
    server_endpoint: Mapped[str | None] = mapped_column(String(500))
    stream_quality: Mapped[str | None] = mapped_column(String(20))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    bandwidth_mbps: Mapped[float | None] = mapped_column(Float)
    packet_loss_percent: Mapped[float | None] = mapped_column(Float)
    encoding_preset: Mapped[str | None] = mapped_column(String(50))
    resolution: Mapped[str | None] = mapped_column(String(50))
    frame_rate: Mapped[int | None] = mapped_column(Integer)
    bit_rate_kbps: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict | None] = mapped_column(JSON)
    participants: Mapped[list | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="cloud_ar_sessions")
