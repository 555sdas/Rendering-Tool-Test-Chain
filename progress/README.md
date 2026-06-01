# XR 测试平台进度总览

最后更新：2026-05-30

本文档按 `target.md` 的 V1 预测试目标记录项目完成情况。当前重点是形成可运行、可演示、可验收的最小闭环：BoatAttack 场景测试、样例数据、性能分析、阈值风险、导出报告、中文文档和命令行启动。

## 当前状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 后端 API | 已完成 V1 主干 | 鉴权、项目、场景资产、测试会话、样本、分析、导出、报告、云 AR、审计 |
| 前端管理端 | 已完成 V1 演示 | 项目页调用真实 API；会话和分析页优先读取后端数据，失败回退内置样例 |
| Unity 插件 | 已完成基础采集包 | 运行时采集、渲染质量场景指标、JSON/CSV 导出、自动创建测试会话并上传、Editor 菜单窗口 |
| BoatAttack 验证 | 已完成 | Unity EditMode 测试通过，结果写入 XML 和 log |
| 演示数据 | 已完成 | 6 个标准场景、300 条样本、阈值规则、云 AR 样例、HTML 报告 |
| 启动脚本 | 已完成 | 无需 PyCharm npm 插件，可用 PowerShell 启动前后端 |
| 文档 | 已更新 | 根 README、后端/前端/Unity README、progress 文档中文化 |

## 本次新增内容

- 新增云 AR 会话接口：`/api/v1/cloud-ar/sessions`
- 新增 HTML 报告生成服务：`POST /api/v1/test-reports/generate-from-session/{session_id}`
- 新增演示数据脚本：`scripts/seed-demo-data.ps1`
- 新增 BoatAttack Unity 测试脚本：`scripts/run-boatattack-editmode.ps1`
- 新增本地全量验证脚本：`scripts/run-local-tests.ps1`
- 前端 `测试会话` 和 `性能分析` 页面改为优先读取后端真实数据
- 前端 `测试会话` 去掉手工“新建测试”，改为展示 Unity 插件自动同步的会话；列表和详情补充 CPU、开始时间、结束时间、耗时
- 后端批量上传接口会从 Unity 样本回填会话元数据：开始/结束时间、耗时、CPU/GPU/内存、系统版本、样本数
- 修复阈值分析中 severity 字段兼容字符串/枚举的问题
- 新增渲染质量评分服务：按光照/阴影、材质/纹理、后处理、物理仿真四类输出可解释扣分和建议
- Unity 插件新增 RenderQualityCollector，采集光源、阴影投射体、材质、透明材质、后处理 Volume、RenderTexture、刚体和碰撞体数量

## target.md 对照进度

| 需求项 | 当前实现 |
| --- | --- |
| ★ 数据采集与测试控制 | Unity 插件、自动测试会话同步、样本接口、BoatAttack EditMode 脚本 |
| # 工具定位与应用范围 | README 和 progress 文档已说明 V1 预测试边界 |
| # 标准测试场景与 3D 模型用例库 | `seed-demo-data` 初始化 6 个 BoatAttack 场景资产 |
| ★ 渲染性能稳定性分析 | FPS、P95/P99 帧时间、长帧、掉帧率、风险等级 |
| # 视觉质量与画面缺陷 | 已新增规则化渲染质量预测试分；缺陷检测仍需截图/参考帧或人工复核输入 |
| # 图像差异与参考帧 | 样例数据支持 SSIM/PSNR/DeltaE 字段；差异图生成 UI 留作 V2 |
| # 资源复杂度与部署负载 | Draw Call、SetPass、三角面、纹理/网格/RT 内存摘要 |
| # 端云/串流基础测试 | 云 AR 会话模型和接口记录时延、带宽、丢包、参与者 |
| # 多终端与业务场景 | 样例覆盖 WindowsEditor 等效平台，文档列出 Quest/PICO/AR 眼镜扩展路径 |
| # 工具链接入能力 | Unity/OpenXR 主线已实现，国产工具链通过配置和 extra_metrics 预留 |
| △ 光照/阴影、物理仿真、主客观评价 | 光照、材质、后处理、物理仿真已有评分规则；专家评分表和截图复核仍是验收补充材料 |
| # 自动化测试编排 | 测试任务模型、PowerShell 脚本和 BoatAttack 一键流程 |
| △ 阈值配置与风险分级 | 阈值规则表、阈值 API、报告风险等级 |
| # 数据导出和归档 | CSV、Excel、JSON 导出，HTML 报告，审计日志 |
| # 报告生成与交付支持 | 自动生成 HTML 样例报告，文档列出交付材料 |

## 演示流程

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\seed-demo-data.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

登录：

```text
admin / Admin123!
```

访问：

- 前端：`http://localhost:5173`
- Swagger：`http://localhost:8002/api/v1/docs`

## 验证结果

- 后端：`18 passed`
- 前端类型检查：通过
- 前端构建：通过，存在 chunk 大小优化提示
- BoatAttack EditMode：1 个测试通过
- Unity 上传链路：已用本地接口模拟批量样本上传，能自动生成/更新会话开始时间、结束时间、耗时和 CPU 型号字段

## 后续建议

- V2 增加真实 XR 头显采集、图像差异算法 UI、WebRTC/CloudXR SDK 真实接入。
- 把报告模板扩展到 PDF/Word。
- 增加长期基准库和更多场景资产许可证留档。
- 将 Pydantic `class Config` 和 FastAPI `on_event` 迁移到新版写法，清理弃用警告。
