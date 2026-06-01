# Unity 插件与 BoatAttack 验证说明

最后更新：2026-05-30

## 插件位置

```text
unity-xr-collector/
```

## 当前能力

- Unity Runtime 采集：帧率、帧时间、CPU/GPU、内存、设备信息。
- 渲染资源指标：Draw Call、三角面、顶点、SetPass、纹理/网格/RT 内存。
- 渲染质量场景指标：光源、实时光源、阴影投射体、反射探针、材质、透明材质、后处理 Volume、RenderTexture、刚体、碰撞体。
- 数据导出：JSON、CSV。
- 数据上传：HTTP 上传到后端样本接口；支持由 Unity 自动创建/同步测试会话。
- Editor 扩展：`XR Test` 菜单和控制窗口。

## BoatAttack 路径

```text
Unity:      E:\unity_install\2022.3.62f3\Editor\Unity.exe
BoatAttack: D:\intellij项目\BoatAttack
```

## 一键运行 EditMode 测试

```powershell
cd C:\Users\fz121\PycharmProjects\Rendering-Tool-Test-Chain
powershell -ExecutionPolicy Bypass -File .\scripts\run-boatattack-editmode.ps1
```

输出：

```text
boatattack-editmode-results.xml
boatattack-editmode.log
```

最近一次验证结果：

```text
EditMode：1 passed, 0 failed
Unity：2022.3.62f3
```

## 与后端联动

正式采集流程建议：

1. 后端创建测试项目，用于归类本次测试结果。
2. Unity 场景挂载 `XRTestManager`。
3. 在 Unity 插件中配置采集频率、会话名称、平台地址、`Project ID` 和 `Scene ID`。
4. 运行场景并采集性能样本。
5. 导出 JSON/CSV，或由 Unity 自动创建测试会话并上传后端。
6. 后端生成分析结果和 HTML 报告。

后端样本接口：

```text
POST /api/v1/data-collection/test-sessions/{session_id}/samples
POST /api/v1/data-collection/test-sessions/{session_id}/samples/batch
```

Unity 插件批量上传建议使用 `samples/batch`，该接口会把 `frameRate` 映射为 `fps`，把 `frameTimeMs` 映射为 `frame_time_ms`，并把 `renderQuality` 写入 `extra_metrics.render_quality`，供后端渲染质量评分服务使用。

当前推荐的自动同步方式：

```text
Platform API Base URL: http://localhost:8002/api/v1
Auto Create Session:  勾选
Project ID:           平台项目 ID
Scene ID:             场景资产 ID
Fixed Upload URL:     留空
Username/Password:    admin / Admin123!
```

插件上传成功后，平台会自动回填测试会话的 CPU 型号、开始时间、结束时间和耗时。项目管理中的“新建项目”不是一次测试，而是测试结果归档分类；Unity 配置中的 `Project ID` 决定结果归到哪个项目。

## V1 边界

- 当前 BoatAttack 命令行测试使用 Unity Test Runner 验证项目可加载、可测试。
- 真实运行时采集需要在 Unity 场景中加入插件组件。
- 设备厂商特有指标如温度、功耗、眼动、FFR 等通过 `extra_metrics` 扩展。
