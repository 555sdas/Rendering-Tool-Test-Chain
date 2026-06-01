import enum
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    DATA_IMPORT = "data_import"
    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"
    TEST_EXECUTE = "test_execute"
    TEST_STOP = "test_stop"
    REPORT_GENERATE = "report_generate"
    REPORT_EXPORT = "report_export"
    PERMISSION_CHANGE = "permission_change"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    THRESHOLD_CREATE = "threshold_create"
    THRESHOLD_UPDATE = "threshold_update"
    THRESHOLD_DELETE = "threshold_delete"
    SCENE_UPLOAD = "scene_upload"
    SCENE_DELETE = "scene_delete"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    username: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
