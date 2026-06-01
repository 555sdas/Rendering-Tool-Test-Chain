import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class AssetType(str, enum.Enum):
    SCENE = "scene"
    MODEL = "model"
    TEXTURE = "texture"
    MATERIAL = "material"
    PREFAB = "prefab"
    SCRIPT = "script"
    CONFIG = "config"


class SceneAsset(Base):
    __tablename__ = "scene_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    asset_type: Mapped[AssetType] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[list | None] = mapped_column(JSON)
    asset_metadata: Mapped[dict | None] = mapped_column(JSON)
    complexity_score: Mapped[float | None] = mapped_column(Float)
    polygon_count: Mapped[int | None] = mapped_column(Integer)
    texture_count: Mapped[int | None] = mapped_column(Integer)
    light_count: Mapped[int | None] = mapped_column(Integer)
    particle_count: Mapped[int | None] = mapped_column(Integer)
    is_public: Mapped[bool] = mapped_column(default=False)
    project_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    test_sessions: Mapped[list["TestSession"]] = relationship("TestSession", back_populates="scene")
    test_tasks: Mapped[list["TestTask"]] = relationship("TestTask", back_populates="scene")
