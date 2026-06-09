# XR 渲染与软硬件适配测试工具链

本项目是面向 `target.md` 技术需求的 V1 预测试平台，重点支撑 XR 应用渲染性能、视觉质量、资源复杂度、终端图形性能、端云/云 AR 协同和验收报告归档。

当前版本使用 BoatAttack 船舶场景作为本地演示样例：

- Unity：`E:\unity_install\2022.3.62f3\Editor\Unity.exe`
- BoatAttack：`D:\intellij项目\BoatAttack`
- 后端：FastAPI + SQLAlchemy + SQLite/PostgreSQL
- 前端：React + TypeScript + Vite + Ant Design
- Unity 插件：`unity-xr-collector`，用于运行时性能采集、导出和上传

## 已实现能力

- 用户登录、JWT 鉴权、角色权限、登录失败锁定和审计日志。
- 项目、场景资产、测试任务、测试会话、性能样本、阈值规则、测试报告管理。
- 性能分析：平均 FPS、P95/P99 帧时间、长帧、掉帧率、内存、温度、资源复杂度摘要。
- 渲染质量评分：按光照/阴影、材质/纹理、后处理、物理仿真四类输出预测试分、扣分项和优化建议。
- 数据导出：CSV、Excel、JSON。
- 报告生成：可从测试会话生成 HTML 样例报告。
- 云 AR 样例记录：支持端云会话、参与者、网络质量、时延和协议边界信息管理。
- BoatAttack 本地验收闭环：Unity EditMode 测试脚本、样例数据灌入、报告生成。
- 命令行启动脚本：不依赖 PyCharm 收费插件即可启动前后端。

## 快速启动

### 1. 初始化演示数据

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\seed-demo-data.ps1
```

默认账号：

```text
用户名：admin
密码：Admin123!
```

### 2. 启动前后端

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

访问地址：

- 前端：`http://localhost:5173`
- 后端接口文档：`http://localhost:8002/api/v1/docs`

也可以分别启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

### 3. 运行 BoatAttack Unity 测试

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-boatattack-editmode.ps1
```

输出文件：

- `boatattack-editmode-results.xml`
- `boatattack-editmode.log`

### 4. 运行本地验证

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local-tests.ps1
```

该脚本会依次运行后端 pytest、前端 TypeScript 检查、ESLint 和前端构建。

## 目录说明

```text
backend/              FastAPI 后端、数据库模型、分析服务、导出与报告服务
frontend/             React 前端管理界面
unity-xr-collector/   Unity 运行时采集插件
scripts/              Windows/Linux 启动、测试、备份、演示脚本
progress/             项目进度、接口、部署、Unity 插件说明
docs/                 分阶段设计、操作、验收和交付文档
target.md             技术需求来源文档
```

## target.md 对应关系

| 需求方向 | 当前落地方式 |
| --- | --- |
| 数据采集与测试控制 | Unity 插件 + 测试会话/样本接口 + BoatAttack 脚本 |
| 标准场景库 | 已初始化 6 个 BoatAttack 标准场景资产记录 |
| 性能稳定性分析 | FPS、帧时间、长帧、掉帧率、阈值规则 |
| 视觉质量辅助分析 | 规则化质量评分、缺陷标记、参考帧指标字段和人工复核边界 |
| 图像差异与参考帧 | 样例数据支持 SSIM/PSNR/DeltaE 字段；差异图生成 UI 留作 V2 |
| 资源复杂度 | Draw Call、SetPass、三角面、纹理/网格/RT 内存摘要 |
| 端云/云 AR | 云 AR 会话接口、网络指标、参与者和协议边界记录 |
| 报告与归档 | HTML 样例报告、CSV/Excel/JSON 数据导出、审计日志 |

Unity 插件的设计、指标和本地接入步骤见：

```text
docs/15-Unity插件设计与本地接入指南.md
```

网页选择 Unity 引擎和 BoatAttack 场景并由后端启动本地测试的流程见：

```text
docs/17-网页启动Unity本地测试.md
```

## 当前边界

V1 是预测试和验收演示版本，不表述为强制认证系统。真实 XR 头显、WebRTC/CloudXR 协议栈、国产渲染工具链和长期基准库属于后续 V2 扩展内容；当前项目已保留数据结构、接口字段和文档说明。
