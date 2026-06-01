# 后端接口说明

最后更新：2026-05-30

后端服务默认运行在：

```text
http://localhost:8002
```

Swagger：

```text
http://localhost:8002/api/v1/docs
```

## 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | 登录，表单格式 `username/password` |
| POST | `/api/v1/auth/refresh` | 刷新令牌 |
| POST | `/api/v1/auth/logout` | 登出 |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/change-password` | 修改密码 |

默认账号：

```text
admin / Admin123!
```

## 项目与场景

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/v1/projects` | 项目列表、创建项目 |
| GET/PUT/DELETE | `/api/v1/projects/{id}` | 项目详情、更新、删除 |
| GET/POST | `/api/v1/scene-assets` | 场景资产列表、创建 |
| GET/PUT/DELETE | `/api/v1/scene-assets/{id}` | 场景资产详情、更新、删除 |

场景资产用于登记 BoatAttack、标准模型、参考帧、配置文件等，字段包含复杂度评分、面数、纹理数量、光源数量、粒子数量、来源和授权说明。

## 数据采集

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/v1/data-collection/test-sessions` | 测试会话列表、创建 |
| GET | `/api/v1/data-collection/test-sessions/{id}` | 会话详情 |
| POST | `/api/v1/data-collection/test-sessions/{id}/start` | 开始会话 |
| POST | `/api/v1/data-collection/test-sessions/{id}/stop` | 停止会话 |
| POST | `/api/v1/data-collection/test-sessions/{id}/samples` | 写入性能样本 |
| POST | `/api/v1/data-collection/test-sessions/{id}/samples/batch` | 批量写入样本，兼容 Unity 导出的 camelCase 字段和 `renderQuality` |
| GET | `/api/v1/data-collection/test-sessions/{id}/samples` | 查询性能样本 |
| GET | `/api/v1/data-collection/test-sessions/{id}/statistics` | 样本统计 |
| GET/POST | `/api/v1/data-collection/test-tasks` | 自动化任务列表、创建 |
| PUT | `/api/v1/data-collection/test-tasks/{id}/status` | 更新任务状态 |

样本字段覆盖 FPS、帧时间、CPU/GPU、内存、温度、Draw Call、三角面、纹理内存、姿态延迟和 `extra_metrics` 扩展字段。

## 性能分析与阈值

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/performance/analysis/{id}/fps` | FPS 统计 |
| GET | `/api/v1/performance/analysis/{id}/frame-time` | 帧时间统计 |
| GET | `/api/v1/performance/analysis/{id}/memory` | 内存统计 |
| GET | `/api/v1/performance/analysis/{id}/thermal` | 温度统计 |
| GET | `/api/v1/performance/analysis/{id}/thresholds` | 阈值检查 |
| GET | `/api/v1/performance/analysis/{id}/full-report` | 完整分析数据 |
| GET | `/api/v1/performance/analysis/{id}/render-quality` | 渲染质量评分，覆盖光照、材质、后处理、物理仿真 |
| GET | `/api/v1/performance/trend` | 多会话趋势对比 |
| GET/POST | `/api/v1/performance/threshold-rules` | 阈值规则列表、创建 |
| GET/PUT/DELETE | `/api/v1/performance/threshold-rules/{id}` | 阈值规则详情、更新、删除 |

完整分析数据新增 `stability_summary`、`resource_summary` 和 `render_quality_assessment`，用于报告生成。

渲染质量评分说明：

- `lighting`：光源/阴影数量、曝光波动、光照闪烁、GPU 和长帧风险。
- `material`：Draw Call、SetPass、材质/透明材质数量、纹理内存。
- `post_processing`：后处理 Volume、RenderTexture 数量和内存、GPU 帧预算风险。
- `physics`：刚体/碰撞体数量、穿模标记、姿态延迟、预测误差和物理相关长帧。

该评分是预测试风险分；没有参考帧、截图证据或专家复核时，不作为最终视觉质量认证结论。

## 报告与导出

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/v1/test-reports` | 报告列表、创建记录 |
| POST | `/api/v1/test-reports/generate-from-session/{id}` | 从测试会话生成 HTML 报告 |
| GET/PUT/DELETE | `/api/v1/test-reports/{id}` | 报告详情、更新、删除 |
| POST | `/api/v1/exports/samples` | 导出样本为 CSV、Excel、JSON |

## 云 AR 协同

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/v1/cloud-ar/sessions` | 云 AR 会话列表、创建 |
| GET/PUT/DELETE | `/api/v1/cloud-ar/sessions/{session_id}` | 会话详情、更新、删除 |

云 AR 会话记录端点、分辨率、帧率、码率、带宽、丢包、时延、参与者和协议支持边界。

## 审计日志

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/audit-logs` | 查询登录、项目、场景、测试、报告、导出等操作日志 |

## 权限概览

| 角色 | 能力 |
| --- | --- |
| admin | 全部管理权限 |
| tester | 执行测试、查看测试、场景管理、云 AR 管理 |
| report_editor | 查看测试、创建报告、导出数据 |
| viewer | 查看测试和报告 |
