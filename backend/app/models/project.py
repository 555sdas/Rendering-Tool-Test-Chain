import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"


class ProjectType(str, enum.Enum):
    RENDER_PERFORMANCE = "渲染性能"
    CLOUD_AR = "云AR协同"
    COLLABORATION = "协同测试"
    GRAPHICS_FEATURE = "图形特性"
    CLOUD_RENDERING = "端云协同"
    VISUAL_QUALITY = "视觉质量"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[str] = mapped_column(String(50), default=ProjectType.RENDER_PERFORMANCE.value)
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.ACTIVE.value)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    creator: Mapped["User"] = relationship("User", back_populates="projects")
    test_sessions: Mapped[list["TestSession"]] = relationship("TestSession", back_populates="project")
    test_tasks: Mapped[list["TestTask"]] = relationship("TestTask", back_populates="project")
