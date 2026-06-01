# Unity XR Collector 插件说明

`unity-xr-collector` 是用于 Unity XR/OpenXR 项目的运行时性能采集插件，服务于 `target.md` 中的数据采集、测试控制、日志记录、结构化导出和平台上传要求。

## 支持能力

- 帧率、帧时间、CPU/GPU 近似利用率、内存和 GC 指标采集。
- Draw Call、三角面、顶点、SetPass、纹理/网格/渲染纹理内存等资源复杂度指标。
- 光源、实时光源、阴影投射体、反射探针、材质、透明材质、后处理 Volume、RenderTexture、刚体和碰撞体数量。
- 设备信息、XR 状态、屏幕分辨率、运行环境信息记录。
- JSON/CSV 导出。
- HTTP 上传到后端数据采集接口，支持自动创建/同步平台测试会话。
- Unity Editor 菜单和测试窗口。

## 安装方式

在 Unity 中打开 Package Manager：

1. 点击 `+`
2. 选择 `Add package from disk...`
3. 选择本目录下的 `package.json`

也可以把本目录作为本地包加入目标 Unity 项目的 `Packages/manifest.json`。

## BoatAttack 本地样例

当前验收演示项目路径：

```text
D:\intellij项目\BoatAttack
```

Unity 路径：

```text
E:\unity_install\2022.3.62f3\Editor\Unity.exe
```

运行 EditMode 测试：

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\run-boatattack-editmode.ps1
```

输出：

- `boatattack-editmode-results.xml`
- `boatattack-editmode.log`

## 核心结构

```text
Runtime/Core/          XRTestManager、XRTestConfig、XRTestSession
Runtime/Collectors/    帧率、帧时间、CPU、GPU、内存、设备信息、渲染质量采集器
Runtime/Data/          PerformanceSample、DeviceInfo
Runtime/Exporters/     JSON、CSV 导出器
Runtime/Network/       HTTP 上传器
Editor/                XR Test 菜单和窗口
```

## 后端上传边界

后端接收性能样本的接口为：

```text
POST /api/v1/data-collection/test-sessions/{session_id}/samples
POST /api/v1/data-collection/test-sessions/{session_id}/samples/batch
```

正式接入真实 XR 设备时，推荐先在平台“项目管理”中新建项目作为归档分类，再在 Unity 插件中填写 `Project ID`、`Scene ID`、平台地址和登录信息。`Fixed Upload URL` 留空并勾选 `Auto Create Session` 时，插件会自动创建测试会话，再把样本上传到 `samples/batch`。该接口兼容 `frameRate`、`frameTimeMs`、`renderQuality` 等导出字段，并会回填 CPU 型号、开始时间、结束时间、耗时、GPU、内存和样本数量。V1 已提供数据结构和上传接口，设备厂商特有指标如温度、功耗、眼动、注视点渲染等可通过 `extra_metrics` 扩展。

本地推荐配置：

```text
Platform API Base URL: http://localhost:8002/api/v1
Auto Create Session:  勾选
Project ID:           平台项目 ID
Scene ID:             场景资产 ID
Fixed Upload URL:     留空
Username/Password:    admin / Admin123!
```

本地接入完整步骤见：

```text
docs/15-Unity插件设计与本地接入指南.md
```

## 渲染质量指标边界

插件当前采集的是客观场景和运行指标，不直接替代人工画质判定：

- 光照：光源数量、实时光源数量、阴影投射体、反射探针。
- 材质：材质槽、去重材质、透明材质。
- 后处理：Volume 数量、RenderTexture 数量。
- 物理仿真：刚体数量、碰撞体数量。

后端会把这些指标与 FPS、帧时间、GPU、纹理内存、姿态延迟等字段合并，输出可解释的预测试质量分。若要形成正式视觉质量结论，还需要补充参考帧、截图证据、SSIM/PSNR/DeltaE 或专家复核记录。
