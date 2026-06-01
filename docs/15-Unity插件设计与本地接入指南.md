# Unity 插件设计与本地接入指南

最后更新：2026-05-30

本文面向 `target.md` 中“子标的二：XR应用渲染性能与视觉质量预测试工具”的 Unity 侧接入。它说明项目总体逻辑、插件需要采集的指标、评分边界，以及如何在本地 Unity/BoatAttack 中配置插件并上传到测试平台。

## 一、项目总体逻辑

你的理解基本正确，但“云”在当前 V1 阶段应理解为“测试平台后端”，本地运行时就是：

```text
Unity/BoatAttack 场景
  -> unity-xr-collector 插件采集样本
  -> 本地导出 JSON/CSV 或上传 HTTP
  -> FastAPI 后端保存到数据库
  -> 后端进行性能稳定性、资源复杂度、渲染质量预测试评分
  -> 前端展示图表/评分
  -> 生成 HTML 测试报告
```

正式部署到服务器时，只需要把上传地址从 `localhost:8002` 换成服务器地址。当前项目不把结论表述为强制认证，定位是预测试、辅助诊断、验收演示和报告归档。

## 二、插件设计目标

Unity 插件位于：

```text
C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain\unity-xr-collector
```

插件承担三件事：

1. 测试控制：开始采集、停止采集、清空样本、导出、上传。
2. 数据采集：采集帧率、帧时间、资源复杂度、设备信息、光照、材质、后处理、物理仿真等指标。
3. 数据交付：导出 JSON/CSV，或上传到后端 `samples/batch` 接口。

## 三、target.md 指标与插件采集设计

| 需求方向 | 采集/评估指标 | Unity 插件采集方式 | 平台处理方式 |
| --- | --- | --- | --- |
| 数据采集与测试控制 | 开始/停止、时间戳、会话、日志、导出 | `XRTestManager`、`XRTestWindow` | 测试会话、样本入库、审计日志 |
| 性能稳定性 | FPS、帧时间、长帧、掉帧率、P95/P99 | `FrameRateCollector`、`FrameTimeCollector` | `PerformanceAnalysisService` 计算统计和风险等级 |
| CPU/GPU/内存 | CPU 近似值、GPU 近似值、总内存、托管内存、显存 | `CpuUsageCollector`、`GpuUsageCollector`、`MemoryCollector` | 资源曲线、峰值、阈值检查 |
| 资源复杂度 | Draw Call、三角面、顶点、SetPass、纹理/网格/RT 内存 | `GpuUsageCollector`、`MemoryCollector` | `resource_summary` 和报告摘要 |
| 光照与阴影 | 活动光源、实时光源、阴影投射体、反射探针、曝光/闪烁标记 | `RenderQualityCollector` 采集数量；曝光/闪烁可通过 `renderQuality` 扩展上传 | 光照维度评分和扣分项 |
| 材质与纹理 | 材质槽、去重材质、透明材质、纹理内存、Draw Call、SetPass | `RenderQualityCollector` + 资源采集器 | 材质维度评分和优化建议 |
| 后处理 | Volume 数量、RenderTexture 数量、RT 内存、GPU 压力 | `RenderQualityCollector` + `MemoryCollector` | 后处理维度评分 |
| 物理仿真 | 刚体、碰撞体、穿模标记、姿态延迟、预测误差、长帧 | `RenderQualityCollector`；穿模/轨迹可通过扩展字段导入 | 物理仿真维度评分 |
| 图像差异 | SSIM、PSNR、DeltaE、差异图 | V1 预留字段；截图/参考帧算法后续扩展 | 评分服务已读取 `reference_frame` 字段 |
| 主观复核 | 专家评分、截图证据、缺陷记录 | 通过 `extra_metrics` 或报告模板录入 | 报告和人工复核结论 |

## 四、质量分数怎么算

当前平台新增了渲染质量预测试评分：

```text
总体质量分 = 光照25% + 材质25% + 后处理25% + 物理仿真25%
```

每个维度从 100 分开始，根据采集指标触发扣分。例如：

- 光源数量缺失、实时光源过多、阴影投射体过多、曝光波动、过曝/欠曝、光照闪烁会扣光照分。
- Draw Call、SetPass、透明材质、纹理内存过高会扣材质分。
- RenderTexture 内存、后处理 Volume、GPU 帧预算压力会扣后处理分。
- 刚体/碰撞体过多、穿模、姿态延迟、预测误差、长帧会扣物理仿真分。

重要边界：

- 如果输入是 `seed-demo-data` 生成的数据，分数是“确定性演示评分”，公式真实，但不是 BoatAttack 画面实测认证。
- 如果 Unity 插件真实运行并上传样本，分数是“基于采集指标的预测试风险分”。
- 如果要形成更严肃的视觉质量结论，需要补充截图、参考帧、SSIM、PSNR、DeltaE、人工复核。

## 五、本地平台启动

在 PowerShell 中启动后端和前端：

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

另开一个 PowerShell：

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

访问：

```text
前端：http://localhost:5173
接口文档：http://localhost:8002/api/v1/docs
账号：admin / Admin123!
```

## 六、在 Unity/BoatAttack 中安装插件

BoatAttack 路径：

```text
D:\intellij项目\BoatAttack
```

Unity 路径：

```text
E:\unity_install\2022.3.62f3\Editor\Unity.exe
```

安装步骤：

1. 用 Unity 打开 `D:\intellij项目\BoatAttack`。
2. 打开 `Window -> Package Manager`。
3. 点击左上角 `+`。
4. 选择 `Add package from disk...`。
5. 选择：

```text
C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain\unity-xr-collector\package.json
```

6. 安装后 Unity 菜单栏会出现 `XR Test`。

## 七、在场景中配置采集器

1. 打开要测试的 BoatAttack 场景，例如 Demo 岛屿或 Water 测试场景。
2. 点击 `XR Test -> Setup -> Create XRTestManager`。
3. 点击 `XR Test -> Open Test Window`。
4. 在窗口里配置：

```text
Session Name: BoatAttack Demo Island Runtime
Collect Interval: 1.0
Frame Rate: 勾选
Frame Time: 勾选
CPU Usage: 勾选
GPU Usage: 勾选
Memory: 勾选
Device Info: 勾选
```

渲染质量相关采集器已经由 `XRTestManager` 自动加入，不需要单独挂组件。

## 八、项目与测试会话的关系

当前推荐逻辑是：平台“项目管理”负责归类，Unity 插件负责生成每次测试会话。

```text
项目 Project
  -> 用来归档某个应用、场景包、版本或测试批次
  -> Unity 配置里的 Project ID 决定结果归到哪个项目

测试会话 Test Session
  -> 一次 Unity 运行采集就是一个会话
  -> 由 Unity 插件上传时自动创建或同步
  -> 后端根据样本回填开始时间、结束时间、耗时、CPU/GPU/内存等元数据
```

所以前端 `测试会话` 页不再建议手工“新建测试”。你只需要在 `项目管理` 中建立项目，记住项目 ID，再把这个 ID 填到 Unity 插件。

如果你确实要调试接口，仍可在 Swagger 中手工调用：

```text
POST /api/v1/data-collection/test-sessions
```

但正式流程应以 Unity 自动同步为准。

## 九、获取上传 Token

PowerShell 获取登录 token：

```powershell
$body = "username=admin&password=Admin123!"
$r = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8002/api/v1/auth/login" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body $body

$r.access_token | Set-Clipboard
$r.access_token
```

控制台输出的一长串字符串就是 Bearer Token。为了方便粘贴，上面命令也会复制到剪贴板。

也可以不手工复制 Token，直接在 Unity 插件里填写用户名和密码，插件会先登录再上传。

## 十、Unity 上传配置

在 `XR Test -> Open Test Window` 的 `Settings` 中配置平台同步：

```text
Platform API Base URL:
http://localhost:8002/api/v1

Auto Create Session:
勾选

Project ID:
平台项目 ID，例如 1

Scene ID:
场景资产 ID，例如 3

Fixed Upload URL:
留空

Username:
admin

Password:
Admin123!
```

保持 `Fixed Upload URL` 留空时，插件会使用自动模式：

```text
登录 -> POST /data-collection/test-sessions 创建会话
     -> POST /data-collection/test-sessions/{session_id}/samples/batch 上传样本
     -> 后端回填 CPU、开始时间、结束时间、耗时、样本数
```

如果你要测试老的固定会话接口，也可以手工填 URL：

在 `XR Test -> Open Test Window` 的 `Settings` 中填：

```text
Fixed Upload URL:
http://localhost:8002/api/v1/data-collection/test-sessions/1/samples/batch

Bearer Token:
粘贴上一步获取的 access_token
```

其中 URL 里的 `1` 要换成你的测试会话 ID。这个固定 URL 模式主要用于接口调试，不是当前推荐路径。

操作流程：

1. 点击 `Start Collection`。
2. 在 Unity 中运行/操作场景一段时间。
3. 点击 `Stop Collection`。
4. 可以先 `Export as JSON` 或 `Export as CSV` 留本地证据。
5. 点击 `Upload / Sync to Platform` 上传到平台。
6. 回到前端 `性能分析 -> 渲染质量` 查看质量分、扣分项和建议。
7. 需要报告时调用 `POST /api/v1/test-reports/generate-from-session/{session_id}` 或在平台报告页面生成。

## 十一、本地导出与上传的区别

| 方式 | 用途 | 说明 |
| --- | --- | --- |
| JSON/CSV 导出 | 留存证据、离线分析、验收附件 | 不依赖后端登录 |
| HTTP 上传 | 平台图表、评分、报告生成 | 需要后端会话 ID 和 Bearer Token |

正式验收建议两者都保留：上传用于平台闭环，导出文件作为原始数据附件。

## 十二、当前 V1 边界与后续扩展

已完成：

- Unity 插件采集性能、资源、渲染质量场景指标。
- 后端保存样本、计算性能稳定性、资源复杂度和质量预测试分。
- 前端展示性能曲线和渲染质量评分。
- 报告中输出评分、扣分项和建议。

仍建议后续扩展：

- 真实截图/关键帧采集。
- 参考帧管理和差异图输出。
- SSIM、PSNR、DeltaE 自动计算。
- PlayMode 自动路线、场景切换、图形特性开关对比。
- 设备级温度、功耗、眼动、FFR、动态分辨率等厂商 SDK 指标。
