import pytest
from fastapi import HTTPException

from app.models.unity_project_lease import UnityProjectLease
from app.services.unity_project_lease_service import UnityProjectLeaseService


def test_acquire_and_release(db):
    service = UnityProjectLeaseService(db)
    path = "/tmp/test-unity-project"
    lease = service.acquire(
        project_path=path,
        owner_type="single_scene",
        owner_id=1,
        parent_task_id=1,
    )
    assert lease.owner_id == 1
    service.release(path)
    assert db.query(UnityProjectLease).count() == 0


def test_acquire_conflict_raises_409(db):
    service = UnityProjectLeaseService(db)
    path = "/tmp/conflict-project"
    service.acquire(
        project_path=path,
        owner_type="single_scene",
        owner_id=1,
        parent_task_id=1,
    )
    with pytest.raises(HTTPException) as exc:
        service.acquire(
            project_path=path,
            owner_type="multi_scene",
            owner_id=2,
            parent_task_id=2,
        )
    assert exc.value.status_code == 409


def test_release_by_owner(db):
    service = UnityProjectLeaseService(db)
    path = "/tmp/owner-release"
    service.acquire(
        project_path=path,
        owner_type="single_scene",
        owner_id=42,
        parent_task_id=42,
    )
    service.release_by_owner("single_scene", 42)
    assert db.query(UnityProjectLease).count() == 0
