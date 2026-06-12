"""Unity 工程运行租约：防止同工程单场景与多场景并发。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.unity_project_lease import UnityProjectLease


DEFAULT_LEASE_HOURS = 6


class UnityProjectLeaseService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def normalize_project_path(project_path: str) -> str:
        return str(Path(project_path).expanduser().resolve())

    @classmethod
    def project_key(cls, project_path: str) -> str:
        normalized = cls.normalize_project_path(project_path)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def purge_expired(self) -> int:
        now = datetime.utcnow()
        rows = self.db.query(UnityProjectLease).filter(UnityProjectLease.expires_at < now).all()
        for row in rows:
            self.db.delete(row)
        if rows:
            self.db.flush()
        return len(rows)

    def acquire(
        self,
        *,
        project_path: str,
        owner_type: str,
        owner_id: int,
        parent_task_id: int | None,
        lease_hours: int = DEFAULT_LEASE_HOURS,
    ) -> UnityProjectLease:
        self.purge_expired()
        normalized = self.normalize_project_path(project_path)
        key = self.project_key(normalized)
        existing = self.db.query(UnityProjectLease).filter(UnityProjectLease.project_key == key).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unity 工程已有活动测试（{existing.owner_type} #{existing.owner_id}），请等待完成后再启动。",
            )
        now = datetime.utcnow()
        lease = UnityProjectLease(
            project_key=key,
            project_path=normalized,
            owner_type=owner_type,
            owner_id=owner_id,
            parent_task_id=parent_task_id,
            heartbeat_at=now,
            expires_at=now + timedelta(hours=lease_hours),
        )
        self.db.add(lease)
        self.db.flush()
        return lease

    def heartbeat(self, project_path: str) -> None:
        key = self.project_key(project_path)
        lease = self.db.query(UnityProjectLease).filter(UnityProjectLease.project_key == key).first()
        if not lease:
            return
        now = datetime.utcnow()
        lease.heartbeat_at = now
        lease.expires_at = now + timedelta(hours=DEFAULT_LEASE_HOURS)
        self.db.flush()

    def release(self, project_path: str | None) -> None:
        if not project_path:
            return
        key = self.project_key(project_path)
        lease = self.db.query(UnityProjectLease).filter(UnityProjectLease.project_key == key).first()
        if lease:
            self.db.delete(lease)
            self.db.flush()

    def release_by_owner(self, owner_type: str, owner_id: int) -> None:
        leases = (
            self.db.query(UnityProjectLease)
            .filter(UnityProjectLease.owner_type == owner_type)
            .filter(UnityProjectLease.owner_id == owner_id)
            .all()
        )
        for lease in leases:
            self.db.delete(lease)
        if leases:
            self.db.flush()
