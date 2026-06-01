# 后端服务说明

后端位于 `backend/`，提供 XR 测试平台的 API、数据模型、分析、导出、报告生成和审计能力。

## 本地运行

项目已配置本地 conda 环境：

```text
C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain\backend\.conda-test\python.exe
```

从项目根目录启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

服务地址：

```text
http://localhost:8002
http://localhost:8002/api/v1/docs
```

默认使用 SQLite：

```text
backend/xr_test.db
```

## 初始化演示数据

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\seed-demo-data.ps1
```

脚本会创建：

- 管理员账号：`admin / Admin123!`
- BoatAttack 项目
- 6 个标准场景资产
- 1 个完成状态的测试会话
- 300 条性能样本
- 光照、材质、后处理、物理仿真质量评分样例指标
- 阈值规则
- 云 AR 样例会话
- 1 份 HTML 样例报告

## 主要 API 模块

| 模块 | 前缀 | 说明 |
| --- | --- | --- |
| 认证 | `/api/v1/auth` | 登录、刷新令牌、当前用户、注册、改密 |
| 用户 | `/api/v1/users` | 用户和角色管理 |
| 项目 | `/api/v1/projects` | 测试项目 CRUD，用于归类 Unity 上传的测试结果 |
| 场景资产 | `/api/v1/scene-assets` | 标准场景、模型、配置资产管理 |
| 数据采集 | `/api/v1/data-collection` | 测试会话、任务、性能样本、Unity 批量样本导入；批量上传会回填 CPU、起止时间、耗时和设备信息 |
| 性能分析 | `/api/v1/performance` | FPS、帧时间、内存、阈值、趋势、渲染质量评分和完整报告数据 |
| 报告 | `/api/v1/test-reports` | 报告记录和从会话生成 HTML 报告 |
| 导出 | `/api/v1/exports` | CSV、Excel、JSON 样本导出 |
| 云 AR | `/api/v1/cloud-ar` | 端云/多人协同样例会话记录 |
| 审计 | `/api/v1/audit-logs` | 关键操作日志查询 |

## 测试

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain\backend
.\.conda-test\python.exe -m pytest
```

当前后端测试结果为 `18 passed`。仍存在 Pydantic `class Config` 和 FastAPI `on_event` 的弃用警告，不影响当前运行。

## 报告生成

接口：

```text
POST /api/v1/test-reports/generate-from-session/{session_id}
```

生成文件默认位于：

```text
backend/uploads/reports/
```

HTML 报告包含测试对象、核心性能指标、资源复杂度、渲染质量预测试评分、阈值风险和优化建议。
