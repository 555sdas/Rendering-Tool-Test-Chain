# Unity 冷启动已知问题（Problem Document）

> 文档用途：记录网页一键冷启动 Unity 时仍未解决的问题，供排查、协作与外部求助使用。  
> 最后更新：2026-06-12
> 状态：**修复已实现，待真实冷启动复核**

## 2026-06-12 测试完成后 Unity 偶发未响应

### 根因定位

历史冷启动任务 `231` 已确认：

```text
08:17:52  测试结果上传成功
08:17:52  XRBatchTestRunner 已安排 Editor 退出
08:17:58  XRBatchTestRunner 调用 EditorApplication.Exit(0)
           Unity 进入原生关闭流程
           日志停止在 Unity.ILPP.Runner.PostProcessingAssemblyLoadContext unloading
08:20:07  Unity 进程最终以 SIGTERM（退出码 -15）结束
```

该任务的测试、采集和上传均已完成。卡点发生在 `EditorApplication.Exit()` 之后，Unity 托管代码和
`EditorApplication.update` 已停止执行，因此插件无法在进程内继续自救。

正常退出日志在 ILPP 卸载后还会出现 `Cleanup mono`、`Application.Shutdown.CleanupEngine` 等记录；
未响应任务没有这些记录。当前证据表明这是 Unity 2022.3 Editor 原生关闭阶段的偶发阻塞，发生位置
集中在 IL Post Processing 程序集卸载附近，而不是测试协程或结果上传仍在运行。

### 已增加的防护

后端冷启动进程监控增加退出看门狗：

- 会话完成上传后，等待 Unity Editor 正常退出 20 秒。
- 超时后向冷启动 Unity 进程组发送 `SIGTERM`，同时回收其子进程。
- 再等待 8 秒仍未退出时发送 `SIGKILL`。
- 强制回收后仍使用已上传完成的会话结果，不把测试误判为失败。
- 该防护仅作用于后端创建的新 Editor 进程，不会终止用户提前打开的热启动 Editor。

真实复核时检查 Runner 日志是否出现：

```text
测试结果已完成上传，等待 Unity Editor 正常退出。
Unity Editor 在结果上传完成后仍未退出，疑似卡在原生关闭流程，开始回收冷启动进程。
```

## 2026-06-11 修复结论

本次通过历史冷启动日志定位到 GC Handle 告警的首次出现时机：

```text
EnteredPlayMode → 插件立即启动采集和 HTTP 协程
→ Asset Pipeline ForceDomainReload
→ Coroutine::CleanupCoroutine / UploadHandlerRaw::~UploadHandlerRaw
→ Release of invalid GC handle
```

根因是采集器在 `EnteredPlayMode` 回调中立即创建进度上报和上传请求，而冷启动随后仍会发生一次强制域重载。旧域中的协程和 `UnityWebRequest` 原生句柄因此被新域清理。

已完成的修复：

- `XRBatchTestRunner` 将采集启动延后到 Play Mode、脚本编译和资源刷新稳定后，并用 `SessionState` 跨域恢复待启动状态。
- 命令行退出只由 `XRBatchTestRunner` 负责；等待退出 Play Mode、编译和资源刷新结束后再调用一次 `EditorApplication.Exit()`。
- 冷启动任务配置在域重载后重新应用，避免场景内默认配置覆盖网页配置。
- CPU 无 Frame Timing 数据时使用 Unity 进程 CPU 时间作为回退；GPU 在 Editor 中使用 `UnityStats.renderTime` 回退。
- Draw Calls、三角面和顶点数在 Editor 无 Camera 渲染数据时，根据活动 Renderer/Mesh 估算场景复杂度。
- 所有阶段上传完整性能、设备和渲染质量字段；后端保留合法的 `0` 值并映射 `graphicsMemoryMB`。
- 前端不再过滤全 0 的资源和 Draw Calls 样本，能够区分“采集值为 0”和“没有样本”。
- Unity 日志新增配置、样本和上传摘要，便于直接核对端到端字段。

自动验证结果：

- 后端：`29 passed`
- 前端：TypeScript 检查、ESLint、生产构建通过
- `git diff --check` 通过

待真实冷启动复核标准：

- 日志中出现“Editor 已稳定，冷启动采集已开始”，且发生在最后一次域重载之后。
- 不再出现来自插件协程或 `UploadHandlerRaw` 的 `Release of invalid GC handle`。
- 样本摘要中 CPU、内存、Draw Calls/三角面、设备信息至少有对应字段；后端结果页不再只有 FPS。

---

## 概述

本项目为 XR 渲染测试工具链：网页通过后端启动 Unity Editor，插件采集性能数据并回传，前端展示实时进度与测试结果。

**冷启动**：用户未预先打开 Unity，后端 `subprocess` 拉起新的 Editor 进程。  
**热启动**：目标 Unity 项目已在 Editor 中打开，后端写入 `pending-task.json` 由插件轮询执行。

冷启动场景下存在两类关联问题：

1. Console 大量 `Release of invalid GC handle` 告警  
2. 测试结果中除 FPS/帧时间外，多项指标不显示或恒为 0  

热启动时上述问题较少出现或不出现。

---

## 问题一：GC Handle 跨域释放告警

### 现象

Unity Console 反复输出：

```text
Release of invalid GC handle. The handle is from a previous domain. The release operation is skipped.
```

- 级别多为 **Warning**，Unity 会跳过无效释放  
- 测试通常仍能跑完，但日志噪音大，不确定是否存在资源泄漏风险  
- **几乎仅在冷启动时出现**，热启动少见  

### 冷启动命令（后端）

```bash
Unity -projectPath <path> \
      -executeMethod XRDataCollector.Editor.XRBatchTestRunner.RunFromCommandLine \
      -xrTaskConfig <task.json> \
      -logFile <log>
```

任务配置中 `quitOnComplete: true`，测试结束后调用 `EditorApplication.Exit()` 关闭 Editor。

### 技术背景

该告警表示：在 **AppDomain 重载**（脚本编译、进/出 Play Mode、Editor 退出）时，某处试图释放属于**上一个脚本域**的 `GCHandle`。

冷启动比热启动经历更多域切换：

```text
Editor 进程启动 → 脚本编译（域重载）→ -executeMethod 执行
→ 进入 Play Mode → 退出 Play Mode → EditorApplication.Exit()
```

常见触发源包括：

- `ProfilerRecorder` 等原生 Profiler 句柄未在域卸载前释放  
- 静态字段持有 `UnityEngine.Object` 引用跨域存活  
- Editor 下 `DontDestroyOnLoad` 单例生命周期异常  
- 域卸载时仍在运行的协程 / `UnityWebRequest`  
- Unity 引擎自身或其它 Package 的行为（不一定来自本插件）

### 已尝试修复（无效）

| 文件 | 措施 |
|------|------|
| `RenderingStatsCollector.cs` | Editor 下改用 `UnityStats`，不使用 `ProfilerRecorder` |
| `DomainLifecycle.cs` | `SubsystemRegistration` 清理 `XRTestManager.Instance` |
| `TestDataUploader.cs` / `UploaderHost` | 域重载时清空单例；Editor 下取消 `DontDestroyOnLoad` |
| `XRTestManager.cs` | 重建采集器前先 `StopCollecting`；`OnDestroy` 不再触发上传 |
| `UnityProgressReporter.cs` | `OnDisable` 停止协程 |
| `XRBatchTestRunner.cs` | `ExitingPlayMode` / `Finish` 清理 `taskConfig` 与事件订阅 |
| `FrameTimingHelper.cs` | 增加 `ResetDomainState()` |

**结论：用户反馈告警仍频繁出现。**

### 相关代码

```
unity-xr-collector/
├── Editor/XRBatchTestRunner.cs
├── Runtime/Core/XRTestManager.cs
├── Runtime/Core/DomainLifecycle.cs
├── Runtime/Network/TestDataUploader.cs      # UploaderHost 单例
├── Runtime/Network/UnityProgressReporter.cs
└── Runtime/Collectors/FrameTimingHelper.cs
```

### 待排查方向

- [ ] 告警首次出现的精确时机（启动 / 进 Play Mode / 退出 / Exit）  
- [ ] 是否来自本插件、`FrameTimingManager`、还是目标项目其它 Package  
- [ ] `EditorApplication.update`（`PollPendingTask`）跨域订阅是否泄漏  
- [ ] 冷启动 `quitOnComplete: true` 退出时序是否与资源释放竞态  
- [ ] 是否应改为不退出 Editor、或使用 Player Build 隔离采集  

---

## 问题二：多项指标不显示（仅 FPS 有数据）

### 现象

冷启动完成测试后，前端**几乎只有 FPS / 帧时间**有曲线，以下数据为空或全 0：

| 缺失项 | 展示位置 |
|--------|----------|
| CPU / GPU 占用率 | 测试中实时面板；测试结果「资源占用」Tab |
| 内存 / 显存 | 同上 |
| Draw Calls | 实时详情区；测试结果「Draw Calls」Tab |
| 渲染质量评分 | 测试结果「渲染质量」Tab |
| 设备信息 | 测试结果「设备信息」Tab |

不确定是「未采集」还是「采集了但未入库/未展示」。

### 端到端数据链路

```text
Unity 采集 (XRTestManager, 两阶段 30s + 30s)
  │
  ├─ 实时路径
  │    UnityProgressReporter
  │    → POST /unity-runner/progress/{task_id}
  │    → WebSocket 广播
  │    → ProjectDetail.tsx 实时面板
  │
  └─ 结果路径
       TestDataUploader
       → POST /data-collection/test-sessions/{id}/samples/batch
       → 数据库 performance_sample 表
       → SessionResultPanel
            ├─ analysisApi.getFullReport()   # 渲染质量、设备信息
            └─ sessionsApi.getSamples()      # 图表数据
```

### Unity 两阶段采集设计

`XRTestManager` 将会话分为两阶段（各默认 30 秒）：

| 阶段 | `collectionPhase` | 设计意图 |
|------|-------------------|----------|
| 阶段 1 | `frame_rate` | 采集 FPS、帧时间 |
| 阶段 2 | `metrics` | 采集 CPU/GPU/内存/Draw Calls/渲染质量/设备信息 |

**历史根因（已部分修复，用户仍无数据）：**

1. `batchCollectors` 仅在阶段 2 才 `StartCollecting()`，阶段 1 样本不含指标  
2. `TestDataUploader` 的 `frame_rate` 分支历史上不传 CPU/GPU/内存等字段  
3. **冷启动竞态**：`XRTestManager.Start()` 可能在 `EnteredPlayMode` 应用网页配置**之前**按场景默认配置开采，导致 `collectCpuUsage` 等开关未生效  

### 前端展示逻辑（0 值会被过滤）

`SessionResultPanel` 中：

```typescript
// 资源占用 Tab：CPU/GPU/内存 全为 0 → 图表空白
filter((item) => item.cpu > 0 || item.gpu > 0 || item.memory > 0)

// Draw Calls Tab：drawCalls 为 0 → 图表空白
filter((item) => item.drawCalls > 0)
```

- **渲染质量**：依赖 `fullReport.render_quality_assessment`，由后端从 `sample.extra_metrics["render_quality"]` 聚合  
- **设备信息**：依赖 `fullReport.session_info.config`，由 batch 上传时首条 sample 的 `deviceInfo` 写入 `TestSession.config`  

### 后端入库字段映射

`data_collection.py` 批量上传解析（camelCase / snake_case 均支持）：

```python
cpu_usage_percent  ← cpuUsagePercent
gpu_usage_percent  ← gpuUsagePercent
memory_mb          ← totalMemoryMB
draw_calls         ← drawCalls
extra_metrics["render_quality"] ← renderQuality（顶层字段合并）
extra_metrics["device_info"]    ← deviceInfo
```

### 已尝试修复（用户反馈仍无数据）

| 文件 | 措施 |
|------|------|
| `XRBatchTestRunner.cs` | `EnteredPlayMode` 用 `SessionState` 重新 `ApplyTaskConfig`；停旧采集再重启 |
| `XRTestManager.cs` | 有 `PendingTaskConfigJson` 时跳过 `Start()` 自启动；两阶段均启动指标采集器 |
| `TestDataUploader.cs` | 所有阶段样本统一上传完整指标字段 |
| `FrameTimingHelper.cs` | 启用 Frame Timing；多帧取 max 改善 CPU/GPU |
| `XRBatchTestRunner.cs` | `PlayerSettings.enableFrameTimingStats = true` |

### 仍怀疑的根因

| # | 假设 | 说明 |
|---|------|------|
| 1 | 配置竞态未彻底消除 | Play Mode 后 `XRTestConfig` 序列化值覆盖网页配置 |
| 2 | CPU/GPU 恒为 0 | `FrameTimingManager` 冷启动未就绪；Frame Timing 有数帧延迟 |
| 3 | Draw Calls 恒为 0 | 场景无 Camera / Game 视图未渲染；`UnityStats` 为 0 |
| 4 | 测试提前结束 | `quitOnComplete` 在 metrics 阶段完成前退出 Editor |
| 5 | 上传成功但字段全 0 | 需查 DB `performance_sample` 实际值 |
| 6 | 前端过滤过严 | `cpu > 0` 导致有微弱数据也不显示 |
| 7 | 设备信息链路断裂 | `DeviceInfoCollector` 未执行或 `deviceInfo` 为 null |

### 相关代码

**Unity：**

```
unity-xr-collector/Runtime/Core/XRTestManager.cs
unity-xr-collector/Editor/XRBatchTestRunner.cs
unity-xr-collector/Runtime/Network/TestDataUploader.cs
unity-xr-collector/Runtime/Network/UnityProgressReporter.cs
unity-xr-collector/Runtime/Collectors/
  ├── CpuUsageCollector.cs
  ├── GpuUsageCollector.cs
  ├── MemoryCollector.cs
  ├── RenderingStatsCollector.cs
  ├── DeviceInfoCollector.cs
  └── RenderQualityCollector.cs
```

**后端：**

```
backend/app/services/unity_runner_service.py    # _launch_unity / _dispatch_to_existing_editor
backend/app/routers/data_collection.py          # batch 样本入库
backend/app/routers/progress_ws.py              # 实时进度
backend/app/services/render_quality_service.py
```

**前端：**

```
frontend/src/pages/Projects/ProjectDetail.tsx
frontend/src/components/SessionResultPanel/index.tsx
frontend/src/components/SessionDeviceInfoPanel/index.tsx
frontend/src/components/RenderQualityPanel/index.tsx
frontend/src/lib/sampleCharts.ts
```

---

## 复现步骤

1. **完全关闭** Unity Editor（确认项目目录无活跃 `UnityLockfile`）  
2. 启动后端（默认 `http://localhost:8002`）与前端（默认 `http://localhost:5173`）  
3. 登录 → 进入项目详情 →「Unity 本地测试」→ 一键启动  
4. 等待约 60 秒测试完成  
5. 检查：  
   - Unity Console：GC handle 告警是否密集出现  
   - 实时面板：CPU/GPU/Draw Calls 是否为 0  
   - 测试结果页：除 FPS 外各 Tab 是否为空  
6. **对照实验**：保持 Editor 打开同一项目，再次启动测试，对比差异  

---

## 建议排查步骤（给接手人）

### 1. 确认断点层级

```text
Unity 是否采到？ → 上传 JSON 是否含字段？ → DB 是否有值？ → API 是否返回？ → 前端是否过滤？
```

### 2. 采集层（Unity）

- 在 `CollectFrameRateSample` / `CollectMetricsSample` 打日志，输出 `cpuUsagePercent`、`drawCalls`、`deviceInfo != null`  
- 检查冷启动 Console 是否有 `[XRBatchTestRunner] 已在 Play Mode 重新应用网页任务配置`  
- 确认 `config.collectCpuUsage` 等在 `StartCollection` 时为 `true`  

### 3. 上传层

- 抓取 `POST .../samples/batch` 请求体，检查 `samples[].cpuUsagePercent`、`drawCalls`、`renderQuality`、`deviceInfo`  
- 对比 `frame_rate` 与 `metrics` 阶段样本字段是否一致  

### 4. 存储层

```sql
SELECT id, fps, cpu_usage_percent, gpu_usage_percent, memory_mb, draw_calls, extra_metrics
FROM performance_sample
WHERE test_session_id = <session_id>
ORDER BY id
LIMIT 5;
```

### 5. 展示层

- 调用 `GET /analysis/sessions/{id}/full-report` 检查 `render_quality_assessment`、`session_info.config`  
- 检查 `SessionResultPanel` 的 `resourceChartData` / `drawCallChartData` 长度是否为 0  

---

## 期望目标

| 目标 | 说明 |
|------|------|
| 冷启动与热启动行为一致 | 指标采集与展示无差异 |
| Console 无大量 GC 告警 | 或确认告警无害且可抑制 |
| 测试结果页完整展示 | 资源占用、Draw Calls、渲染质量、设备信息均有真实数据 |
| 实时面板同步 | 测试中即可看到 CPU/GPU/内存/Draw Calls 等非零值 |

---

## 环境信息（排查时请填写）

| 项 | 值 |
|----|-----|
| Unity Editor 版本 | _待填_ |
| 渲染管线 | Built-in / URP / HDRP |
| 操作系统 | macOS |
| 目标 Unity 项目路径 | _待填_ |
| GC 告警首次出现时机 | _待填_ |
| 冷启动 `launch_mode` | `new_editor` |
| 热启动 `launch_mode` | `existing_editor` |

### 建议附件

- [ ] Unity Console 完整日志（含 GC 告警前后 20 行）  
- [ ] `-logFile` 指向的 `Editor.log` 片段  
- [ ] 一次冷启动测试的 `performance_sample` 样例 JSON（1–2 条）  
- [ ] `POST .../samples/batch` 请求体片段  

---

## 问题状态总览

| 问题 | 状态 | 优先级 |
|------|------|--------|
| GC handle 跨域告警（冷启动） | ❌ 未解决 | P2（噪音/潜在泄漏） |
| CPU/GPU/内存不显示（冷启动） | ❌ 未解决 | **P0** |
| Draw Calls 不显示（冷启动） | ❌ 未解决 | **P0** |
| 渲染质量不显示（冷启动） | ❌ 未解决 | **P0** |
| 设备信息不显示（冷启动） | ❌ 未解决 | **P0** |
| 热启动路径 | ⚠️ 相对正常（待确认） | P1 |
| 测试能跑完并上传 | ✅ 基本可用 | — |

---

## 参考文档

- [网页启动 Unity 本地测试](../17-网页启动Unity本地测试.md)
- [Unity 插件操作文档](../13-Unity插件操作文档.md)
- [数据采集与测试控制核心](../03-数据采集与测试控制核心.md)
