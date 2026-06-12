# 渲染质量缺失指标解决方案

> 依据：`docs/problems/render-quality-missing-metrics.md`  
> 目标：解决渲染质量子项“已勾选但暂无数据”的语义、采集、聚合与评分问题，同时维持现有指标选择、冷启动、热启动、实时进度、上传和历史会话正常运行。  
> 文档用途：供 Cursor 分阶段实施，不包含本次代码改动。  
> 编写日期：2026-06-12

---

## 1. 实施结论

问题文档对数据缺口的判断基本正确，但解决方案不能简单理解为“给所有空字段补一个数值”。

当前 21 个质量子项实际分为三类：

1. **通用 Unity 环境下可可靠采集**  
   场景数量、Draw Calls、纹理内存、RenderTexture 内存、GPU 帧预算、长帧等。
2. **需要满足运行环境或采用启发式方法才可采集**  
   曝光异常、后处理配置警告、穿模风险。
3. **没有外部真值或业务埋点时，通用插件无法可靠测量**  
   XR 姿态延迟、预测误差，以及严格意义上的“物理导致长帧”。

因此正确路线是：

1. **先建立质量指标能力与状态契约，停止用 `null` 或 `-1` 猜测原因。**
2. **将状态明确区分为 `skipped / available / unavailable / missing / failed`。**
3. **优先补齐可可靠采集项。**
4. **条件支持项使用 Provider 或明确标记为启发式测量。**
5. **无法可靠测量的项目必须诚实显示“当前环境不支持”，不得填伪数据。**
6. **评分只使用 `available` 数据；采集完整度与质量风险分分开表达。**

---

## 2. 当前实现基线

### 2.1 已完成的能力

仓库当前已经具备：

- `test_scope`、`execution_plan`、`requestedMetricIds`、`supportMetricIds`；
- `collectRenderingStats` 与 `collectRenderQuality` 独立采集开关；
- Unity 质量细分项布尔配置；
- 后端 `SCOPED_METRIC_BINDINGS`，按本次 scope 输出主要依据；
- 前端对已勾选但值为 `null` 的项目显示“暂无数据”；
- 会话快照、冷启动和热启动配置恢复链路；
- 合法数值 `0` 的后端入库支持。

这些现有能力应保留，不应重新设计指标选择体系。

### 2.2 当前核心缺口

- 指标目录将全部质量子项标记为 `collect_and_analyze`，但部分指标实际上没有通用采集实现。
- Unity 只上报质量数值，没有上报每个指标的能力、状态和失败原因。
- 后端只能通过“字段存在、值为 `-1`、字段缺失”推断状态，无法区分不支持和采集失败。
- 部分布尔异常项使用默认 `0`，即使 Unity 从未实现检测，后端仍可能显示为“未检出”。
- 评分规则对缺数处理不一致，可能产生虚高分或不合理扣分。
- `graphicsMemoryMB` 被回退映射成 `texture_memory_mb`，语义不准确。

---

## 3. 产品语义与状态模型

### 3.1 统一状态枚举

质量子项统一使用：

| 状态 | 条件 | UI 展示 | 评分行为 |
|------|------|---------|----------|
| `skipped` | 本次 `test_scope` 未选择 | 未纳入本次测试 | 不参与评分和完整度分母 |
| `available` | 已选择且有可靠有效数据，真实 `0` 也属于此状态 | 展示数值 | 正常参与评分 |
| `unavailable` | 已选择，但运行环境、设备或缺少 Provider 导致无法测量 | 当前环境不支持，并显示原因 | 不参与风险扣分，计入能力覆盖说明 |
| `missing` | 已选择、能力声明支持，但整个测试没有有效数据 | 采集缺失 | 不做业务风险扣分，降低数据完整度 |
| `failed` | 采集过程明确报错 | 采集失败，并显示错误摘要 | 不做业务风险扣分，降低数据完整度并提示修复 |

`pending` 仅用于测试进行中的实时界面，不应出现在已完成结果中。

### 3.2 不再使用模糊语义

- `null` 只代表结果没有数值，具体原因必须由 `metric_status` 解释。
- `-1` 仅作为旧 Unity 插件的兼容哨兵，不作为新协议的正式状态。
- `0` 始终是有效数值，不能代表跳过、不支持或失败。
- “未检出异常”只有在检测器确实运行成功后才能显示为 `0`。

### 3.3 风险分与证据完整度分离

建议质量结果同时输出：

```json
{
  "overall_score": 87.5,
  "data_completeness": 0.76,
  "confidence_grade": "B",
  "coverage_summary": {
    "selected": 21,
    "available": 16,
    "unavailable": 3,
    "missing": 1,
    "failed": 1
  }
}
```

规则：

- `overall_score` 只评价已获得的质量风险证据；
- `data_completeness` 评价已选择指标中有可靠数据的比例；
- `confidence_grade` 反映分数可信度；
- 不应通过扣质量风险分来惩罚平台自身采集缺失；
- 如果产品必须对验收完整度设门槛，应单独设置“完整度不达标”，不要混入画质风险分。

---

## 4. 指标能力分级

指标目录应新增：

```python
{
    "measurement_tier": "native | derived | conditional | provider_required",
    "implementation_status": "implemented | planned | unsupported",
    "measurement_semantics": "...",
    "required_capabilities": [],
    "fallback_policy": "unavailable | derived_proxy",
}
```

目录与默认选择规则：

- `implementation_status=implemented` 的指标可保持当前默认开启；
- `planned/unsupported` 且没有可用 Provider 的指标，内置默认应关闭，避免“默认全选”天然产生缺失结果；
- 若管理员或用户仍主动选择条件指标，选择器应显示“需要 Camera / XR Provider / 显式 Probe”等能力提示；
- 后端启动时不得因条件指标暂不可用而拒绝整个任务，应允许测试完成并返回 `unavailable`；
- 指标目录描述的是产品能力，运行时 manifest 描述的是本次环境实际能力，两者不能混用。

### 4.1 可可靠补齐或已有实现

| scope ID | 建议测量方式 | 状态 |
|----------|--------------|------|
| `lighting.active_lights` | 活动 `Light` 数量 | 已实现 |
| `lighting.realtime_lights` | 实时 `Light` 数量 | 已实现 |
| `lighting.shadow_casters` | 开启阴影投射的 Renderer 数量 | 已实现 |
| `lighting.reflection_probes` | ReflectionProbe 数量 | 已实现 |
| `materials.material_slots` | Renderer 材质槽数量 | 已实现 |
| `materials.unique_materials` | Material 去重数量 | 已实现 |
| `materials.transparent_materials` | 透明材质启发式识别 | 已实现但应标记 heuristic |
| `materials.draw_calls` | RenderingStatsCollector | 已实现 |
| `materials.texture_memory` | 对已加载 Texture 调用运行时内存统计并求和 | 应补齐 |
| `post_processing.volumes` | SRP Volume 数量；Built-in 管线需单独适配 | 部分实现 |
| `post_processing.render_textures` | 已加载 RenderTexture 数量 | 已实现 |
| `post_processing.render_texture_memory` | 对 RenderTexture 求运行时内存大小并求和 | 应补齐 |
| `post_processing.gpu_frame_budget` | GPU 帧时或 GPU 占用 + 目标帧预算衍生 | 可补齐 |
| `physics.rigidbodies` | Rigidbody 数量 | 已实现 |
| `physics.colliders` | Collider 数量 | 已实现 |
| `physics.long_frames` | 总帧时间长帧代理指标 | 已实现衍生，但名称需澄清 |

### 4.2 条件支持或启发式指标

| scope ID | 限制 | 建议 |
|----------|------|------|
| `lighting.exposure_artifacts` | 需要 Camera 输出和像素亮度采样；BatchMode、无 Camera 或异步读回不支持时无法测量 | 实现可选图像分析 Provider；无能力时 `unavailable` |
| `post_processing.warnings` | 不存在跨 Built-in/URP/HDRP 的统一“后处理警告”接口 | 先实现配置审计 Provider，不要伪装成运行时异常检测 |
| `physics.penetration` | 通用插件无法判断哪些重叠属于异常；`Physics.ComputePenetration` 全场扫描成本高且可能误报 | 仅对显式标记对象或业务事件 Provider 检测；否则 `unavailable` |

### 4.3 必须由设备或业务 Provider 提供

| scope ID | 原因 | 默认行为 |
|----------|------|----------|
| `physics.pose_latency` | 需要输入采样时间、预测显示时间、实际呈现时间或设备扩展 | 无 Provider 时 `unavailable` |
| `physics.prediction_error` | 需要预测姿态与后续实际姿态的可比真值 | 无 Provider 时 `unavailable` |

### 4.4 需要修正名称或语义

`physics.long_frames` 当前来自总帧时间，无法证明长帧由物理系统导致。

推荐二选一：

1. 第一版将展示名调整为“测试期间长帧（物理关联参考）”，并标记 `derived_proxy`；
2. 后续增加 FixedUpdate/Physics.Simulate 专项耗时 Provider 后，再恢复“物理导致长帧”的严格语义。

不得继续把普通长帧直接解释为物理导致。

---

## 5. 端到端状态协议

### 5.1 Unity 上报测量清单

建议在 batch 上传根对象新增 `qualityMetricManifest`，每次会话上传一次：

```json
{
  "qualityMetricManifest": [
    {
      "id": "materials.texture_memory",
      "status": "available",
      "reasonCode": null,
      "measurementTier": "native",
      "provider": "UnityResourceMemoryProvider",
      "providerVersion": 1,
      "validSampleCount": 30,
      "errorCount": 0,
      "unit": "MB"
    },
    {
      "id": "physics.pose_latency",
      "status": "unavailable",
      "reasonCode": "provider_not_installed",
      "measurementTier": "provider_required",
      "provider": null,
      "providerVersion": null,
      "validSampleCount": 0,
      "errorCount": 0,
      "unit": "ms"
    }
  ]
}
```

选择列表仍以 `session.config.test_scope` 为准；manifest 只描述 Unity 实际能力与执行结果。

### 5.2 原因码

建议使用稳定原因码，前端映射中文：

```text
not_selected
provider_not_installed
unsupported_render_pipeline
camera_not_available
xr_runtime_not_available
reference_truth_not_available
batchmode_not_supported
collector_not_started
no_valid_samples
collector_exception
legacy_plugin_no_manifest
```

不要把完整异常堆栈直接返回前端；堆栈保留在 Unity 日志，manifest 中保存简短错误摘要。

### 5.3 存储策略

第一阶段不建议新增数据库表，避免扩大迁移范围。

将 manifest 合并保存到：

```text
TestSession.config.quality_metric_manifest
```

同时在 `TestTask.result_summary` 保存最后一次执行摘要，便于任务诊断。

后续如果需要跨会话统计采集器可靠性，再增加独立状态表。

### 5.4 后端状态判定优先级

`RenderQualityService` 构建每个子项状态时：

```text
scope 未选择
→ skipped

manifest 明确 unavailable / failed
→ 使用 manifest 状态和原因

manifest 声明 available 且聚合有有效值
→ available

manifest 声明 available 但无有效值
→ missing

旧会话没有 manifest
→ 根据数值、-1、execution_plan 和插件版本推断
```

旧会话推断结果必须标记 `inferred=true`，避免与新协议的明确状态混淆。

### 5.5 Manifest 上线前的止损规则

在完整 Provider 和 manifest 完成前，建议先修正会产生错误结论的默认行为：

- `post_processing_warning_count`、曝光异常 flag 等未运行检测器时应为 `None`，不能默认 `0`；
- `long_frame_count` 只有存在有效帧时间样本时才能为 `0`，否则应为 `None`；
- `texture_memory_mb` 不再从 `graphicsMemoryMB` 回退；
- `SCOPED_METRIC_BINDINGS` 的 getter 不应使用默认 `0` 掩盖未实现采集；
- 评分中的“缺少采集”判断必须先检查该细分项是否被选择；
- 暂未实现且无 Provider 的指标应在后端静态能力表中直接标记 `unavailable`。

这些止损规则能立即减少虚假“未检出”和错误评分，同时保持旧上传格式可用。

---

## 6. Unity 插件实施方案

### 6.1 公共测量接口

不要继续把所有逻辑塞进 `RenderQualityCollector`。建议增加：

```text
unity-xr-collector/Runtime/Quality/IQualityMetricProvider.cs
unity-xr-collector/Runtime/Quality/QualityMetricResult.cs
unity-xr-collector/Runtime/Quality/QualityMetricManifest.cs
unity-xr-collector/Runtime/Quality/QualityMetricCoordinator.cs
```

Provider 接口职责：

```csharp
string MetricId { get; }
QualityMetricCapability ProbeCapability(XRTestConfig config);
void StartCollecting();
void Collect(ref PerformanceSample sample);
QualityMetricExecutionSummary StopCollecting();
```

要求：

- Provider 明确报告支持性，不支持时给出原因码；
- Provider 异常不能终止整个测试，应记录 `failed`；
- 低频场景扫描与每帧采集分开；
- 所有 Provider 遵循现有域重载清理规则；
- 默认不创建新的持续网络请求或跨域静态句柄。

### 6.2 优先补齐内存指标

新增 `ResourceMemoryCollector` 或扩展现有内存采集：

- `textureMemoryMB`：遍历已加载 `Texture`，排除 `RenderTexture` 后求运行时内存总和；
- `renderTextureMemoryMB`：遍历已加载 `RenderTexture` 求运行时内存总和；
- 可选 `meshMemoryMB`：遍历 Mesh 求和。

实施注意：

- `Resources.FindObjectsOfTypeAll` 与运行时内存统计可能较重，不要每帧执行；
- 按采集间隔或固定低频率采样；
- 缓存对象集合并处理场景切换；
- 明确数值是“已加载资源内存估算”，不是 GPU 驱动精确显存；
- 不再将 `graphicsMemoryMB` 冒充 `textureMemoryMB`。

对应修改：

- `PerformanceSample` 增加 `textureMemoryMB`、`renderTextureMemoryMB`、可选 `meshMemoryMB`；
- `TestDataUploader` 上报对应字段；
- 实时进度可按需增加字段，但不阻塞第一阶段结果修复。

### 6.3 GPU 帧预算

将其定义为后端衍生指标，不必在 Unity 新增独立数值字段。

输入：

- GPU 帧时或 GPU 占用；
- P95 帧时间；
- 目标刷新率或目标帧预算。

要求：

- `execution_plan` 自动启用 GPU 与帧时间支撑采集；
- 若运行环境无法提供 GPU 数据，状态为 `unavailable`；
- 输出预算使用率、目标预算和数据来源；
- 不要仅凭 GPU 百分比断言后处理导致超预算。

### 6.4 曝光异常 Provider

建议作为可选 Provider 实现，不作为所有场景的强制能力。

建议算法：

- 明确选择用于测试的 Camera；
- 对低分辨率目标进行异步 GPU Readback；
- 计算亮度直方图、平均亮度、高低亮度像素比例；
- 以时间窗口计算曝光波动；
- 输出 `exposure_delta`、`overexposure_count`、`underexposure_count`；
- 闪烁检测应设置最小持续时间和阈值，避免场景正常运动误报。

不支持条件：

- 无有效 Camera；
- BatchMode 或当前平台不支持异步读回；
- 图形 API 不支持；
- 用户未授权图像采样。

这些情况必须上报 `unavailable`，不能上报 `0`。

### 6.5 后处理警告 Provider

第一版建议定义为“后处理配置审计”，而不是无法保证的运行时警告检测。

可检测：

- 不支持的 Volume/Profile 类型；
- 重叠全局 Volume；
- 高成本效果组合；
- 无效或过多 RenderTexture；
- 当前管线缺少预期后处理支持；
- Camera 后处理配置不一致。

不同渲染管线使用 Adapter：

```text
BuiltInPostProcessingProvider
UrpPostProcessingProvider
HdrpPostProcessingProvider
```

没有对应 Adapter 时上报 `unsupported_render_pipeline`。

### 6.6 穿模与碰撞异常 Provider

不要默认对全场景 Collider 两两检测。

推荐支持两种模式：

1. **业务事件模式**：目标项目调用插件公开 API 上报穿模、异常碰撞事件；
2. **显式监控模式**：只对带 `XRQualityPenetrationProbe` 标记的关键对象执行 `Physics.ComputePenetration`。

结果必须注明检测覆盖范围。无 Probe 或业务事件接入时，状态为 `unavailable`，不是“0 次异常”。

### 6.7 姿态延迟与预测误差 Provider

定义扩展接口，但默认插件不伪造数据：

```text
IXrPoseTimingProvider
IXrPredictionErrorProvider
```

可由目标项目、设备 SDK 或 OpenXR 扩展实现。

没有 Provider、没有时间戳或没有真值轨迹时：

- `physics.pose_latency = unavailable`
- `physics.prediction_error = unavailable`
- 原因码分别为 `provider_not_installed` 或 `reference_truth_not_available`

### 6.8 配置应用和日志

继续沿用现有：

- `test_scope`
- `execution_plan`
- `qualityMetricChecks`
- `SessionState` 跨域恢复

新增日志：

```text
[QualityMetrics] materials.texture_memory: available, provider=UnityResourceMemoryProvider
[QualityMetrics] physics.pose_latency: unavailable, reason=provider_not_installed
[QualityMetrics] lighting.exposure_artifacts: failed, reason=collector_exception
```

---

## 7. 上传与后端入库方案

### 7.1 修正字段语义

立即停止：

```text
graphicsMemoryMB → texture_memory_mb
```

正确映射：

```text
textureMemoryMB → texture_memory_mb
renderTextureMemoryMB → render_texture_memory_mb
meshMemoryMB → mesh_memory_mb
graphicsMemoryMB → extra_metrics.graphics_memory_mb
```

如果需要长期查询 graphics memory，应后续增加独立数据库列；不要占用纹理内存字段。

### 7.2 Batch schema 扩展

扩展 batch 上传 schema 接受：

```text
qualityMetricManifest
textureMemoryMB
renderTextureMemoryMB
meshMemoryMB
```

要求：

- 兼容旧上传 payload；
- 合法 `0` 保持为 `0`；
- `-1` 不写入统计列；
- manifest 合并至会话 config 时保留原 `test_scope`；
- 上传结果返回 manifest 保存摘要，便于 Unity 日志确认。

### 7.3 聚合结构

建议 `RenderQualityService._build_stats()` 返回：

```json
{
  "values": {},
  "observations": {
    "materials.texture_memory": {
      "valid_sample_count": 30,
      "source": "performance_samples.texture_memory_mb"
    }
  },
  "manifest": {},
  "metric_status": {}
}
```

避免继续让一个扁平 `stats` 字典同时承担数值、来源、状态和能力判断。

### 7.4 兼容旧会话

旧会话没有 manifest 时：

- scope 未选：`skipped`；
- 存在合法值，包括 `0`：`available`；
- 值全部为 `-1`：推断为 `skipped` 或 `unavailable`，并标记 `inferred`；
- execution plan 声明应采集但无值：`missing`；
- 无 execution plan：`missing`，原因 `legacy_plugin_no_manifest`。

不得回写或篡改旧会话原始样本。

---

## 8. 后端评分实施方案

### 8.1 每个分类输出子项状态

`RenderQualityCategory` 增加：

```json
{
  "metric_status": {
    "materials.texture_memory": {
      "status": "available",
      "reason_code": null,
      "value_keys": ["peak_texture_memory_mb"],
      "valid_sample_count": 30,
      "inferred": false
    }
  },
  "coverage": {
    "selected": 5,
    "available": 4,
    "unavailable": 1,
    "missing": 0,
    "failed": 0
  }
}
```

`category.metrics` 可以继续保留，保证旧前端兼容。

### 8.2 规则级依赖

将评分条件改为显式规则定义：

```python
{
    "id": "materials.texture_memory.high",
    "requires_metrics": ["materials.texture_memory"],
    "condition": ...,
    "points": 8,
}
```

规则执行：

- 所有依赖指标 `available`：执行风险判断；
- 依赖指标 `skipped`：不执行；
- 依赖指标 `unavailable`：不执行，写入能力说明；
- 依赖指标 `missing/failed`：不执行风险扣分，降低完整度并写入采集问题；
- 不允许 `None` 静默绕过且没有解释。

### 8.3 去除不正确的跨项扣分

当前评分中存在“即使用户没有选择相关子项，也可能依据其他 stats 扣分”的风险。

必须保证：

- 光照类 GPU 压力规则只有选择相应 GPU/帧预算证据时才执行；
- 材质纹理内存规则只有真实纹理内存 `available` 时执行；
- 后处理 GPU 压力不能仅凭全局 GPU 高就归因后处理；
- 物理长帧代理指标必须标明是相关性，不是因果归因。

### 8.4 完整度与结果等级

建议：

| 完整度 | 可信度等级 |
|--------|------------|
| `>= 0.9` | A |
| `>= 0.75` | B |
| `>= 0.5` | C |
| `< 0.5` | D |

当完整度过低时：

- 仍可显示已有证据计算的风险分；
- 明确标注“结论可信度较低”；
- 报告不应只显示一个看似确定的总分。

---

## 9. 前端展示方案

### 9.1 API 类型

扩展：

```text
frontend/src/api/analysis.ts
```

新增：

```typescript
type QualityMetricStatus = 'skipped' | 'available' | 'unavailable' | 'missing' | 'failed';
```

以及 `metric_status`、`coverage`、`data_completeness`、`confidence_grade` 类型。

### 9.2 主要依据列表

每行根据状态展示：

| 状态 | 文案与颜色 |
|------|------------|
| `available` | 正常数值 |
| `skipped` | 灰色“未纳入本次测试” |
| `unavailable` | 灰蓝色“当前环境不支持”，Tooltip 显示原因 |
| `missing` | 橙色“采集缺失” |
| `failed` | 红色“采集失败” |

前端不再根据 `value == null` 自行决定统一显示“暂无数据”，必须优先读取后端 `metric_status`。

### 9.3 卡片摘要

每个质量分类显示：

```text
已选择 5 项 / 有效 3 项 / 不支持 1 项 / 缺失 1 项
```

总体区域增加：

- 风险分；
- 数据完整度；
- 结论可信度；
- 未安装 Provider 或环境不支持的提示。

### 9.4 历史和旧接口兼容

若后端没有返回 `metric_status`：

- 使用现有 `null → 暂无数据` fallback；
- 显示“旧版本会话，缺失原因无法判断”；
- 不影响当前页面打开。

---

## 10. 分阶段实施顺序

每个阶段完成后都应可单独上线。

### 阶段 0：固定真实基线

执行：

- 保存一个全选质量子项的真实冷启动会话；
- 保存一个全选质量子项的真实热启动会话；
- 导出 task json、Unity 日志、batch payload、数据库样本和 full report；
- 区分真实会话与 seed demo 会话。

验收：

- 明确每个质量子项当前实际来源和缺失位置；
- 后续修改可与基线逐项对比。

### 阶段 1：状态与能力契约

实施：

- 指标目录增加 measurement tier 和实现状态；
- 尚未实现且无 Provider 的指标从内置默认范围中移除，并在选择器中标记能力前提；
- Unity 增加质量 manifest；
- batch 上传保存 manifest；
- 后端输出 `metric_status` 和 coverage；
- 前端展示五态；
- 评分暂保持原阈值，但先消除模糊“暂无数据”。

验收：

- 全部已选择质量子项都有明确状态；
- 未实现项显示 `unavailable`，不再伪装为成功或模糊缺失；
- 旧会话仍可查看。

### 阶段 2：补齐可靠采集项

优先实施：

- 真实纹理内存；
- RenderTexture 内存；
- GPU 帧预算衍生结果；
- Render Pipeline/Volume 支持性检测；
- 修正 graphics memory 映射；
- 长帧代理语义说明。

验收：

- 可可靠实现项在支持环境下均为 `available`；
- 合法 `0` 正确显示；
- 无对应管线时状态为 `unavailable`。

### 阶段 3：评分可信度改造

实施：

- 规则级依赖；
- 风险分与数据完整度分离；
- missing/failed 不再静默跳过；
- 报告输出覆盖率和可信度。

验收：

- 同一份 scope 与 metric status 必然产生一致评分解释；
- 无数据不会导致虚高且没有说明；
- 平台采集失败不会被当作业务质量风险。

### 阶段 4：条件 Provider

按价值和项目需要实施：

- 曝光图像分析；
- 后处理配置审计；
- 显式穿模 Probe；
- XR 姿态延迟 Provider；
- XR 预测误差 Provider。

验收：

- Provider 缺失时明确 `unavailable`；
- Provider 安装后状态转为 `available`；
- Provider 异常不影响其他指标和测试上传。

---

## 11. 测试方案

### 11.1 后端单元测试

至少覆盖：

- scope 未选时状态为 `skipped`；
- manifest 声明不支持时状态为 `unavailable`；
- manifest 声明支持且有真实 `0` 时状态为 `available`；
- manifest 声明支持但无值时状态为 `missing`；
- manifest 声明异常时状态为 `failed`；
- 旧会话无 manifest 时正确推断并标记 `inferred`；
- `graphicsMemoryMB` 不再写入 `texture_memory_mb`；
- 纹理与 RenderTexture 内存字段正确入库；
- missing/failed 不触发业务风险扣分；
- 风险分与完整度分别计算；
- 不同 scope 下规则级依赖正确。

### 11.2 Unity 测试

至少覆盖：

- Provider capability probe；
- 真实 `0` 与 unsupported 的区别；
- 纹理与 RenderTexture 内存求和；
- Provider 抛异常后 manifest 为 `failed`，其他采集器继续；
- 没有 Camera 时曝光 Provider 为 `unavailable`；
- 非支持渲染管线时后处理 Provider 为 `unavailable`；
- 无 XR Provider 时姿态延迟与预测误差为 `unavailable`；
- 域重载、冷启动、热启动后 manifest 不丢失。

### 11.3 端到端测试矩阵

| 场景 | 预期 |
|------|------|
| 全选，普通 Editor 场景 | 已实现项有值；需要 Provider 项明确 unavailable |
| 全选，无 Camera 场景 | 曝光检测 unavailable，不显示 0 或 missing |
| 全选，非 URP/HDRP | 对应后处理能力显示 unsupported_render_pipeline |
| 仅选择纹理内存 | execution_plan 启用资源内存采集；有真实结果 |
| 仅选择姿态延迟 | 无 Provider 时明确 unavailable；测试仍完成 |
| 选择穿模检测但没有 Probe | unavailable，而非 0 次异常 |
| Provider 主动抛错 | 该项 failed；其他指标和上传正常 |
| 真实数值为 0 | available + 0 |
| 旧版本历史会话 | 可查看，并提示状态为推断 |
| 冷启动 / 热启动 | 状态和结果一致，不受域重载影响 |

---

## 12. 关键文件改动清单

### Unity

```text
unity-xr-collector/Runtime/Quality/IQualityMetricProvider.cs                 # 新增
unity-xr-collector/Runtime/Quality/QualityMetricResult.cs                    # 新增
unity-xr-collector/Runtime/Quality/QualityMetricManifest.cs                  # 新增
unity-xr-collector/Runtime/Quality/QualityMetricCoordinator.cs               # 新增
unity-xr-collector/Runtime/Collectors/RenderQualityCollector.cs
unity-xr-collector/Runtime/Collectors/MemoryCollector.cs
unity-xr-collector/Runtime/Data/PerformanceSample.cs
unity-xr-collector/Runtime/Network/TestDataUploader.cs
unity-xr-collector/Runtime/Network/UnityProgressReporter.cs                  # 可选实时状态
unity-xr-collector/Editor/XRBatchTestRunner.cs
```

### 后端

```text
backend/app/services/test_metric_catalog.py
backend/app/services/test_scope_service.py
backend/app/services/render_quality_service.py
backend/app/services/performance_analysis_service.py
backend/app/routers/data_collection.py
backend/app/schemas/performance_sample.py
backend/app/services/report_generation_service.py
backend/tests/test_render_quality_metric_status.py                            # 新增
backend/tests/test_data_collection_batch.py
```

### 前端

```text
frontend/src/api/analysis.ts
frontend/src/components/RenderQualityPanel/index.tsx
frontend/src/components/RenderQualityPanel/RenderQualityPanel.css
frontend/src/lib/renderQualityLabels.ts
```

---

## 13. 明确禁止的实施方式

- 不要为了消灭“暂无数据”给未实现指标默认填 `0`。
- 不要把 `graphicsMemoryMB` 当成纹理内存。
- 不要在无 Camera 时声称完成曝光异常检测。
- 不要在无 XR 时间戳或真值时估算姿态延迟、预测误差。
- 不要把所有 Collider 重叠都判定为穿模异常。
- 不要把普通长帧直接归因为物理系统。
- 不要让采集器异常终止整个测试流程。
- 不要用同一个质量风险分表达采集完整度。
- 不要删除现有 `category.metrics`，应通过新增状态字段保持旧前端兼容。
- 不要让旧会话读取当前能力状态后被重新解释为新会话结果。
- 不要使用 seed demo 数据验证真实 Unity 采集完整性。

---

## 14. Cursor 执行检查单

- [ ] 指标目录声明真实 measurement tier 与实现状态
- [ ] Unity 为每个已选择质量子项输出明确 manifest 状态
- [ ] batch 上传兼容旧 payload 并保存 manifest
- [ ] 后端输出全量 `metric_status` 和 coverage
- [ ] 前端区分跳过、不支持、缺失、失败和真实 0
- [ ] 纹理内存与 RenderTexture 内存使用独立真实字段
- [ ] graphics memory 不再冒充纹理内存
- [ ] 无可靠测量方法的指标默认 unavailable
- [ ] 评分规则具有明确指标依赖
- [ ] 风险分和数据完整度分离
- [ ] 旧会话继续可查看
- [ ] Provider 异常不影响其他采集与上传
- [ ] 后端测试通过
- [ ] 前端 `npm run check && npm run lint && npm run build` 通过
- [ ] Unity 编译通过
- [ ] 至少完成一次冷启动和热启动真实回归

---

## 15. 最终验收定义

只有同时满足以下条件，才算解决该问题：

1. 用户选择的每个质量子项都有明确、可解释的最终状态；
2. 支持且已实现的指标能够产出可靠数据，包括真实 `0`；
3. 不支持或需要外部 Provider 的指标诚实显示原因；
4. 不再使用显存冒充纹理内存，也不再用伪数值填补缺失；
5. 评分只使用可靠、状态为 `available` 的证据；
6. 风险分、完整度与可信度能够分别解释；
7. 前端不再仅用模糊的“暂无数据”覆盖所有情况；
8. 历史会话、冷启动、热启动、实时进度和上传流程无回归。
