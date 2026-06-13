import pytest
from fastapi import HTTPException

from app.models.test_batch import TestBatch as BatchModel
from app.models.test_task import TestTask as TaskModel
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
    task = TaskModel(name="Running", task_type="unity_local_render_test", status="running")
    db.add(task)
    db.flush()
    service = UnityProjectLeaseService(db)
    path = "/tmp/conflict-project"
    service.acquire(
        project_path=path,
        owner_type="single_scene",
        owner_id=task.id,
        parent_task_id=task.id,
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


def test_acquire_reclaims_terminal_single_scene_lease(db):
    task = TaskModel(name="Completed", task_type="unity_local_render_test", status="completed")
    db.add(task)
    db.flush()
    service = UnityProjectLeaseService(db)
    path = "/tmp/completed-owner"
    service.acquire(
        project_path=path,
        owner_type="single_scene",
        owner_id=task.id,
        parent_task_id=task.id,
    )

    replacement = service.acquire(
        project_path=path,
        owner_type="multi_scene",
        owner_id=99,
        parent_task_id=None,
    )

    assert replacement.owner_type == "multi_scene"
    assert db.query(UnityProjectLease).count() == 1


def test_acquire_reclaims_terminal_multi_scene_lease(db):
    parent = TaskModel(name="Parent", task_type="unity_multi_scene_orchestration", status="completed")
    db.add(parent)
    db.flush()
    batch = BatchModel(
        project_id=1,
        parent_task_id=parent.id,
        status="cancelled",
        scene_total=2,
        unity_project_path="/tmp/completed-batch",
        unity_project_key=UnityProjectLeaseService.project_key("/tmp/completed-batch"),
    )
    db.add(batch)
    db.flush()
    service = UnityProjectLeaseService(db)
    service.acquire(
        project_path=batch.unity_project_path,
        owner_type="multi_scene",
        owner_id=batch.id,
        parent_task_id=parent.id,
    )

    replacement = service.acquire(
        project_path=batch.unity_project_path,
        owner_type="single_scene",
        owner_id=88,
        parent_task_id=None,
    )

    assert replacement.owner_type == "single_scene"
    assert db.query(UnityProjectLease).count() == 1
