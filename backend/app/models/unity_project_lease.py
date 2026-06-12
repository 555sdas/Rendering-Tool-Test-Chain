from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UnityProjectLease(Base):
    __tablename__ = "unity_project_leases"

    project_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_path: Mapped[str] = mapped_column(String(1024))
    owner_type: Mapped[str] = mapped_column(String(32))
    owner_id: Mapped[int] = mapped_column(Integer)
    parent_task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("test_tasks.id"))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
