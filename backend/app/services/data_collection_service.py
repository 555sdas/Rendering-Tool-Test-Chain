from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.models.test_session import TestSession, TestSessionStatus
from app.models.performance_sample import PerformanceSample
from app.models.test_task import TestTask, TestTaskStatus


class DataCollectionService:
    def __init__(self, db: Session):
        self.db = db

    def create_test_session(
        self,
        name: str,
        device_model: Optional[str] = None,
        os_version: Optional[str] = None,
        xr_runtime: Optional[str] = None,
        app_version: Optional[str] = None,
        scene_id: Optional[int] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        config: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> TestSession:
        session = TestSession(
            name=name,
            device_model=device_model,
            os_version=os_version,
            xr_runtime=xr_runtime,
            app_version=app_version,
            scene_id=scene_id,
            user_id=user_id,
            project_id=project_id,
            config=config,
            description=description,
            status=TestSessionStatus.PENDING,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def start_test_session(self, session_id: int) -> TestSession:
        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise ValueError("测试会话不存在")
        session.status = TestSessionStatus.RUNNING
        session.started_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    def stop_test_session(self, session_id: int, status: TestSessionStatus = TestSessionStatus.COMPLETED) -> TestSession:
        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise ValueError("测试会话不存在")
        session.status = status
        session.ended_at = datetime.utcnow()
        if session.started_at:
            session.duration_seconds = (session.ended_at - session.started_at).total_seconds()
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_performance_sample(
        self,
        test_session_id: int,
        timestamp: datetime,
        frame_time_ms: Optional[float] = None,
        fps: Optional[float] = None,
        cpu_usage_percent: Optional[float] = None,
        gpu_usage_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        battery_level: Optional[float] = None,
        battery_temperature: Optional[float] = None,
        draw_calls: Optional[int] = None,
        triangle_count: Optional[int] = None,
        vertex_count: Optional[int] = None,
        set_pass_calls: Optional[int] = None,
        texture_memory_mb: Optional[float] = None,
        mesh_memory_mb: Optional[float] = None,
        render_texture_memory_mb: Optional[float] = None,
        gc_collect_count: Optional[int] = None,
        gc_allocated_mb: Optional[float] = None,
        screen_resolution: Optional[str] = None,
        tracking_state: Optional[str] = None,
        prediction_error_ms: Optional[float] = None,
        pose_latency_ms: Optional[float] = None,
        extra_metrics: Optional[dict] = None,
    ) -> PerformanceSample:
        sample = PerformanceSample(
            test_session_id=test_session_id,
            timestamp=timestamp,
            frame_time_ms=frame_time_ms,
            fps=fps,
            cpu_usage_percent=cpu_usage_percent,
            gpu_usage_percent=gpu_usage_percent,
            memory_mb=memory_mb,
            battery_level=battery_level,
            battery_temperature=battery_temperature,
            draw_calls=draw_calls,
            triangle_count=triangle_count,
            vertex_count=vertex_count,
            set_pass_calls=set_pass_calls,
            texture_memory_mb=texture_memory_mb,
            mesh_memory_mb=mesh_memory_mb,
            render_texture_memory_mb=render_texture_memory_mb,
            gc_collect_count=gc_collect_count,
            gc_allocated_mb=gc_allocated_mb,
            screen_resolution=screen_resolution,
            tracking_state=tracking_state,
            prediction_error_ms=prediction_error_ms,
            pose_latency_ms=pose_latency_ms,
            extra_metrics=extra_metrics,
        )
        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def get_test_session_samples(
        self,
        test_session_id: int,
        skip: int = 0,
        limit: int = 1000,
    ) -> list[PerformanceSample]:
        return (
            self.db.query(PerformanceSample)
            .filter(PerformanceSample.test_session_id == test_session_id)
            .order_by(PerformanceSample.timestamp)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_session_statistics(self, test_session_id: int) -> dict:
        samples = self.db.query(PerformanceSample).filter(
            PerformanceSample.test_session_id == test_session_id
        ).all()

        if not samples:
            return {}

        def avg(values):
            valid = [v for v in values if v is not None]
            return sum(valid) / len(valid) if valid else None

        def min_val(values):
            valid = [v for v in values if v is not None]
            return min(valid) if valid else None

        def max_val(values):
            valid = [v for v in values if v is not None]
            return max(valid) if valid else None

        return {
            "sample_count": len(samples),
            "fps_avg": avg([s.fps for s in samples]),
            "fps_min": min_val([s.fps for s in samples]),
            "fps_max": max_val([s.fps for s in samples]),
            "frame_time_avg_ms": avg([s.frame_time_ms for s in samples]),
            "cpu_usage_avg": avg([s.cpu_usage_percent for s in samples]),
            "gpu_usage_avg": avg([s.gpu_usage_percent for s in samples]),
            "memory_avg_mb": avg([s.memory_mb for s in samples]),
            "memory_peak_mb": max_val([s.memory_mb for s in samples]),
            "battery_temp_avg": avg([s.battery_temperature for s in samples]),
            "draw_calls_avg": avg([s.draw_calls for s in samples]),
            "triangle_count_avg": avg([s.triangle_count for s in samples]),
        }

    def create_test_task(
        self,
        name: str,
        task_type: str,
        creator_id: Optional[int] = None,
        project_id: Optional[int] = None,
        scene_id: Optional[int] = None,
        config: Optional[dict] = None,
        target_devices: Optional[list] = None,
        priority: int = 0,
        description: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> TestTask:
        task = TestTask(
            name=name,
            task_type=task_type,
            creator_id=creator_id,
            project_id=project_id,
            scene_id=scene_id,
            config=config,
            target_devices=target_devices,
            priority=priority,
            description=description,
            scheduled_at=scheduled_at,
            status=TestTaskStatus.PENDING,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_test_task_status(
        self,
        task_id: int,
        status: TestTaskStatus,
        error_message: Optional[str] = None,
        result_summary: Optional[dict] = None,
    ) -> TestTask:
        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ValueError("测试任务不存在")

        task.status = status
        if status == TestTaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.utcnow()
        if status in [TestTaskStatus.COMPLETED, TestTaskStatus.FAILED, TestTaskStatus.CANCELLED]:
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
        if error_message:
            task.error_message = error_message
        if result_summary:
            task.result_summary = result_summary

        self.db.commit()
        self.db.refresh(task)
        return task
