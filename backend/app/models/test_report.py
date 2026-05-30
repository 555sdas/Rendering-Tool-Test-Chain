import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    HTML = "html"


class TestReport(Base):
    __tablename__ = "test_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int | None] = mapped_column(Integer)
    test_session_ids: Mapped[list | None] = mapped_column(JSON)
    creator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    format: Mapped[ReportFormat] = mapped_column(String(20), default=ReportFormat.PDF.value)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[dict | None] = mapped_column(JSON)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    creator: Mapped["User"] = relationship("User", back_populates="test_reports")
