#!/usr/bin/env python3
"""初始化 V1 验收演示数据。

默认写入本地 SQLite 数据库，内容包括：
- 管理员账号 admin / Admin123!
- BoatAttack 项目与 6 个标准场景用例
- 阈值规则、自动化任务、测试会话、性能样本、云 AR 会话
- 1 份 HTML 样例测试报告
"""

from __future__ import annotations

import math
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./xr_test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-local-dev-only")

from app.core.security import get_password_hash
from app.database import SessionLocal, init_db
from app.models.cloud_ar_session import CloudARSession, CloudARSessionStatus
from app.models.performance_sample import PerformanceSample
from app.models.project import Project, ProjectStatus, ProjectType
from app.models.scene_asset import SceneAsset
from app.models.test_session import TestSession, TestSessionStatus
from app.models.test_task import TestTask, TestTaskStatus
from app.models.threshold_rule import ThresholdRule, ThresholdSeverity
from app.models.user import User, UserRole, UserStatus
from app.services.report_generation_service import ReportGenerationService


UNITY_EXE = r"E:\unity_install\2022.3.62f3\Editor\Unity.exe"
BOATATTACK_PATH = r"D:\intellij项目\BoatAttack"


def get_or_create_admin(db) -> User:
    user = db.query(User).filter(User.username == "admin").first()
    if user:
        return user
    user = User(
        username="admin",
        email="admin@example.com",
        password_hash=get_password_hash("Admin123!"),
        full_name="Administrator",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        login_attempts=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def upsert_project(db, admin: User) -> Project:
    project = db.query(Project).filter(Project.name == "BoatAttack XR渲染性能预测试").first()
    if not project:
        project = Project(
            name="BoatAttack XR渲染性能预测试",
            description="使用 Unity BoatAttack 船舶场景作为 XR 渲染性能、视觉质量和资源复杂度预测试样例。",
            project_type=ProjectType.RENDER_PERFORMANCE.value,
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        db.add(project)
    else:
        project.description = "使用 Unity BoatAttack 船舶场景作为 XR 渲染性能、视觉质量和资源复杂度预测试样例。"
        project.status = ProjectStatus.ACTIVE.value
    db.commit()
    db.refresh(project)
    return project


def upsert_scene_assets(db, project: Project) -> list[SceneAsset]:
    scenes = [
        ("BoatAttack 主菜单", "Assets/scenes/main_menu.unity", "低复杂度入口场景", 2.0, 42000, 28, 6, 0),
        ("BoatAttack 静态岛屿", "Assets/scenes/static_Island.unity", "中复杂度室外岛屿场景，覆盖水面、植被与阴影。", 6.8, 480000, 96, 18, 12),
        ("BoatAttack Demo 岛屿", "Assets/scenes/demo_Island.unity", "高复杂度动态船舶与海面演示场景。", 8.3, 820000, 154, 25, 34),
        ("Benchmark 静态岛屿", "Assets/scenes/Testing/benchmark_island-static.unity", "用于基准对比的静态参考帧场景。", 7.1, 530000, 102, 19, 8),
        ("Benchmark 飞行路线", "Assets/scenes/Testing/benchmark_island-flythrough.unity", "用于视角路线切换、长帧和加载稳定性测试。", 8.6, 910000, 168, 23, 16),
        ("Water 水体测试", "Assets/scenes/Testing/Water.unity", "覆盖反射、透明、水体材质和画面一致性检测。", 5.6, 310000, 74, 12, 20),
    ]
    assets: list[SceneAsset] = []
    for name, path, desc, score, polygons, textures, lights, particles in scenes:
        asset = db.query(SceneAsset).filter(SceneAsset.name == name, SceneAsset.project_id == project.id).first()
        metadata = {
            "source": "Unity Technologies BoatAttack sample",
            "license_note": "用于本地功能验证和预测试演示，正式对外交付需复核 BoatAttack 原项目许可证。",
            "unity_project_path": BOATATTACK_PATH,
            "render_pipeline": "URP",
            "coverage": ["性能稳定性", "资源复杂度", "视觉质量辅助分析"],
        }
        if not asset:
            asset = SceneAsset(
                name=name,
                description=desc,
                asset_type="scene",
                file_path=str(Path(BOATATTACK_PATH) / path),
                file_size=0,
                version="2022.3",
                tags=["BoatAttack", "Unity", "URP", "XR预测试"],
                asset_metadata=metadata,
                complexity_score=score,
                polygon_count=polygons,
                texture_count=textures,
                light_count=lights,
                particle_count=particles,
                is_public=True,
                project_id=project.id,
            )
            db.add(asset)
        else:
            asset.description = desc
            asset.asset_metadata = metadata
            asset.complexity_score = score
            asset.polygon_count = polygons
            asset.texture_count = textures
            asset.light_count = lights
            asset.particle_count = particles
        assets.append(asset)
    db.commit()
    return db.query(SceneAsset).filter(SceneAsset.project_id == project.id).order_by(SceneAsset.id).all()


def upsert_threshold_rules(db, project: Project) -> None:
    rules = [
        ("XR平均FPS低于60", "fps", "<", 60, ThresholdSeverity.WARNING, "平均帧率低于公共展示和基础XR体验建议线。"),
        ("P95帧时间超过16.67ms", "frame_time_ms", ">", 16.67, ThresholdSeverity.WARNING, "P95帧时间超过60Hz预算。"),
        ("内存占用超过4096MB", "memory_mb", ">", 4096, ThresholdSeverity.CRITICAL, "峰值内存接近移动XR设备风险区。"),
        ("Draw Call超过180", "draw_calls", ">", 180, ThresholdSeverity.INFO, "Draw Call偏高，建议检查合批、材质和渲染队列。"),
    ]
    for name, metric, operator, value, severity, desc in rules:
        rule = db.query(ThresholdRule).filter(ThresholdRule.name == name, ThresholdRule.project_id == project.id).first()
        if not rule:
            rule = ThresholdRule(
                name=name,
                description=desc,
                metric_name=metric,
                operator=operator,
                threshold_value=value,
                severity=severity.value,
                project_id=project.id,
                auto_alert=True,
                alert_channels=["platform"],
            )
            db.add(rule)
        else:
            rule.description = desc
            rule.metric_name = metric
            rule.operator = operator
            rule.threshold_value = value
            rule.severity = severity.value
            rule.is_active = True
    db.commit()


def build_render_quality_metrics(
    index: int,
    wave: float,
    long_frame: bool,
    texture_memory_mb: float,
    render_texture_memory_mb: float,
    pose_latency_ms: float,
    prediction_error_ms: float,
) -> dict:
    exposure_delta = abs(math.sin(index / 41.0)) * 0.08 + (0.16 if index in {143, 211} else 0)
    shadow_flicker = index in {143, 211}
    overexposure = exposure_delta > 0.18
    post_warning = long_frame and render_texture_memory_mb > 230
    physics_warning = long_frame and index in {211, 260}

    return {
        "lighting": {
            "active_light_count": 25,
            "realtime_light_count": 19,
            "shadow_caster_count": int(58 + wave * 8),
            "reflection_probe_count": 4,
            "exposure_delta": round(exposure_delta, 3),
            "shadow_flicker": shadow_flicker,
            "overexposure": overexposure,
            "underexposure": False,
        },
        "material": {
            "material_count": 78,
            "unique_material_count": 54,
            "transparent_material_count": 16,
            "texture_memory_mb": round(texture_memory_mb, 2),
            "material_warning": False,
        },
        "post_processing": {
            "post_process_volume_count": 3,
            "render_texture_count": 7,
            "render_texture_memory_mb": round(render_texture_memory_mb, 2),
            "post_processing_warning": post_warning,
        },
        "physics": {
            "rigidbody_count": 22,
            "collider_count": 96,
            "penetration_event_count": 0,
            "pose_latency_ms": round(pose_latency_ms, 2),
            "prediction_error_ms": round(prediction_error_ms, 2),
            "physics_warning": physics_warning,
        },
        "reference_frame": {
            "ssim": 0.972 if not overexposure else 0.943,
            "psnr": 34.8 if not overexposure else 29.6,
            "delta_e": 2.7 if not overexposure else 5.9,
        },
    }


def upsert_demo_session(db, admin: User, project: Project, scene: SceneAsset) -> TestSession:
    session = db.query(TestSession).filter(TestSession.name == "BoatAttack Demo 岛屿 - Editor预测试").first()
    now = datetime.utcnow().replace(microsecond=0)
    if not session:
        session = TestSession(
            name="BoatAttack Demo 岛屿 - Editor预测试",
            description="基于 BoatAttack 船舶场景生成的 V1 验收演示样例数据。",
            status=TestSessionStatus.COMPLETED.value,
            device_model="WindowsEditor 等效XR运行平台",
            os_version="Windows 11",
            xr_runtime="Unity Editor / OpenXR兼容边界",
            app_version="BoatAttack / Unity 2022.3.62f3",
            scene_id=scene.id,
            user_id=admin.id,
            project_id=project.id,
            config={
                "unity_exe": UNITY_EXE,
                "unity_project_path": BOATATTACK_PATH,
                "test_platform": "EditMode + synthetic runtime metrics",
                "resolution": "1920x1080",
                "refresh_rate": 60,
                "graphics_api": "Direct3D11",
                "notes": "真实运行采集由 Unity 插件执行；本样例用于平台闭环验收与报告演示。",
            },
            started_at=now - timedelta(minutes=5),
            ended_at=now,
            duration_seconds=300,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        session.status = TestSessionStatus.COMPLETED.value
        session.scene_id = scene.id
        session.project_id = project.id
        session.user_id = admin.id
        session.started_at = now - timedelta(minutes=5)
        session.ended_at = now
        session.duration_seconds = 300
        db.query(PerformanceSample).filter(PerformanceSample.test_session_id == session.id).delete()
        db.commit()

    random.seed(20260530)
    start = session.started_at or (now - timedelta(minutes=5))
    samples: list[PerformanceSample] = []
    for i in range(300):
        wave = math.sin(i / 18.0)
        jitter = random.uniform(-1.8, 1.8)
        long_frame = i in {72, 143, 211, 260}
        fps = max(42.0, 68.0 + wave * 4.5 + jitter - (12 if long_frame else 0))
        frame_time = 1000.0 / fps + (18 if long_frame else random.uniform(-0.3, 0.7))
        texture_memory_mb = 820 + wave * 42 + random.uniform(-10, 12)
        mesh_memory_mb = 340 + wave * 20 + random.uniform(-6, 8)
        render_texture_memory_mb = 220 + wave * 14 + random.uniform(-4, 5)
        pose_latency_ms = 18 + random.uniform(-2, 3)
        prediction_error_ms = 2.0 + random.uniform(-0.4, 0.6)
        render_quality = build_render_quality_metrics(
            i,
            wave,
            long_frame,
            texture_memory_mb,
            render_texture_memory_mb,
            pose_latency_ms,
            prediction_error_ms,
        )
        samples.append(
            PerformanceSample(
                test_session_id=session.id,
                timestamp=start + timedelta(seconds=i),
                frame_time_ms=round(frame_time, 3),
                fps=round(fps, 2),
                cpu_usage_percent=round(48 + wave * 8 + random.uniform(-3, 4), 2),
                gpu_usage_percent=round(64 + wave * 10 + random.uniform(-4, 5), 2),
                memory_mb=round(2480 + i * 1.6 + random.uniform(-12, 18), 2),
                battery_level=None,
                battery_temperature=round(36.5 + i * 0.01 + random.uniform(-0.2, 0.25), 2),
                draw_calls=int(132 + wave * 20 + random.randint(-8, 12)),
                triangle_count=int(760000 + wave * 80000 + random.randint(-15000, 22000)),
                vertex_count=int(1120000 + wave * 90000 + random.randint(-18000, 26000)),
                set_pass_calls=int(72 + wave * 10 + random.randint(-4, 6)),
                texture_memory_mb=round(texture_memory_mb, 2),
                mesh_memory_mb=round(mesh_memory_mb, 2),
                render_texture_memory_mb=round(render_texture_memory_mb, 2),
                gc_collect_count=1 if i in {120, 240} else 0,
                gc_allocated_mb=round(64 + random.uniform(0, 8), 2),
                screen_resolution="1920x1080",
                tracking_state="Editor模拟",
                prediction_error_ms=round(prediction_error_ms, 2),
                pose_latency_ms=round(pose_latency_ms, 2),
                extra_metrics={
                    "visual_quality": "未发现黑屏；水体反射场景建议人工复核高光闪烁。",
                    "render_quality": render_quality,
                    "evidence": "boatattack-editmode-results.xml",
                    "graphics_feature": "URP Medium Pipeline",
                },
            )
        )
    db.bulk_save_objects(samples)
    db.commit()
    return session


def upsert_task_and_cloud_session(db, admin: User, project: Project, scene: SceneAsset, session: TestSession) -> None:
    task = db.query(TestTask).filter(TestTask.name == "BoatAttack 一键预测试任务流").first()
    if not task:
        task = TestTask(
            name="BoatAttack 一键预测试任务流",
            description="加载 BoatAttack 场景、运行 Unity EditMode 验证、灌入性能样例并生成报告。",
            status=TestTaskStatus.COMPLETED.value,
            task_type="automation",
            priority=8,
            project_id=project.id,
            scene_id=scene.id,
            creator_id=admin.id,
            config={
                "steps": ["启动Unity批处理", "运行EditMode测试", "采集/导入性能样本", "阈值分析", "生成报告"],
                "unity_exe": UNITY_EXE,
                "boatattack_path": BOATATTACK_PATH,
            },
            target_devices=["WindowsEditor", "OpenXR等效平台"],
            started_at=session.started_at,
            completed_at=session.ended_at,
            duration_seconds=session.duration_seconds,
            result_summary={"session_id": session.id, "result": "completed", "sample_count": 300},
        )
        db.add(task)
    else:
        task.status = TestTaskStatus.COMPLETED.value
        task.result_summary = {"session_id": session.id, "result": "completed", "sample_count": 300}

    cloud = db.query(CloudARSession).filter(CloudARSession.session_id == "cloudar-boatattack-demo").first()
    if not cloud:
        cloud = CloudARSession(
            session_id="cloudar-boatattack-demo",
            name="BoatAttack 云渲染链路边界样例",
            description="记录端云/串流能力边界：当前V1提供数据结构、会话记录和报告字段，真实WebRTC/CloudXR接入需按项目协议扩展。",
            status=CloudARSessionStatus.CLOSED.value,
            user_id=admin.id,
            project_id=project.id,
            scene_id=scene.id,
            server_endpoint="webrtc://demo-edge-renderer.local/boatattack",
            stream_quality="demo",
            latency_ms=42.5,
            bandwidth_mbps=35.0,
            packet_loss_percent=0.2,
            encoding_preset="H.265 balanced",
            resolution="1920x1080",
            frame_rate=60,
            bit_rate_kbps=18000,
            config={
                "support_boundary": "V1提供数据记录、阈值和报告；协议栈接入按供应商SDK适配。",
                "interference": "模拟弱网0.2%丢包",
            },
            participants=[
                {"user": "tester-a", "role": "operator", "sync_delay_ms": 18},
                {"user": "tester-b", "role": "observer", "sync_delay_ms": 24},
            ],
            started_at=session.started_at,
            ended_at=session.ended_at,
            duration_seconds=session.duration_seconds,
        )
        db.add(cloud)
    else:
        cloud.latency_ms = 42.5
        cloud.packet_loss_percent = 0.2
        cloud.status = CloudARSessionStatus.CLOSED.value
    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        admin = get_or_create_admin(db)
        project = upsert_project(db, admin)
        scenes = upsert_scene_assets(db, project)
        upsert_threshold_rules(db, project)
        session = upsert_demo_session(db, admin, project, scenes[2])
        upsert_task_and_cloud_session(db, admin, project, scenes[2], session)
        report = ReportGenerationService(db).generate_session_html_report(
            session.id,
            admin.id,
            title="BoatAttack XR渲染性能预测试样例报告",
            description="target.md V1 验收演示报告。",
        )
        print("演示数据初始化完成")
        print(f"管理员账号: admin / Admin123!")
        print(f"项目ID: {project.id}")
        print(f"测试会话ID: {session.id}")
        print(f"样例报告: {report.file_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
