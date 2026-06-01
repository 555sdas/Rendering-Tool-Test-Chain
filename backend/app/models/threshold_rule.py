import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class ThresholdSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ThresholdRule(Base):
    __tablename__ = "threshold_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[ThresholdSeverity] = mapped_column(String(20), default=ThresholdSeverity.WARNING.value)
    device_filter: Mapped[str | None] = mapped_column(String(100))
    scene_filter: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    project_id: Mapped[int | None] = mapped_column(Integer)
    auto_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_channels: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
