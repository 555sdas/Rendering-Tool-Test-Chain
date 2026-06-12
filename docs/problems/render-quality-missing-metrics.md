# 渲染质量结果「暂无数据」问题报告（Problem Document）

> 文档用途：说明测试结束后渲染质量评分页部分子项显示「暂无数据」的原因，分析对评分系统的影响，并给出供 Codex 实施的修复方向。  
> 最后更新：2026-06-11  
> 状态：**待修复**

---

## 1. 问题概述

用户在**测试指标选择器**中勾选了大量子项（基础性能 6 项 + 渲染质量 21 项），测试完成后在**分析页 / 结果面板 → 渲染质量**四宫格中的「主要依据」里，部分子项显示为 **「暂无数据」**。

用户疑问：**是没测？还是测了但没显示？**

### 1.1 结论（先答）

| 展示文案 | 实际含义 |
|----------|----------|
| **未测试**（整个大类标签） | 该质量大类未纳入 `test_scope`，不参与评分 |
| **跳过**（基础性能 Tab / 顶部 Statistic） | 该基础指标未纳入 `test_scope` |
| **暂无数据**（渲染质量「主要依据」子项） | **已纳入本次测试范围**，但后端在样本中**未聚合到任何有效数值**（`null`） |

因此：**「暂无数据」≠ 用户没勾选；≠ 整个大类未测试。**  
它表示：**范围已纳入，但采集链或聚合链未产出可展示数据。**

这对评分系统有直接影响：部分扣分规则在缺数时会触发「缺少采集，评分可信度降低」，而另一些规则在 `None` 时**静默不扣分**，造成**用户感知（已测）与评分行为（部分跳过）不一致**。

---

## 2. 现象与复现

### 2.1 典型现象

- 测试范围横幅显示「共纳入 N 项」数量正确（含用户勾选的质量子项）。
- 渲染质量卡片「主要依据」中：
  - 部分子项有数值（如活动光源数量、Draw Call）。
  - 部分子项显示 **「暂无数据」**（如曝光波动、穿模异常、姿态延迟、RenderTexture 内存等）。
- 同一大类仍可能参与评分并出现扣分项（说明大类 `tested=true`，并非整类跳过）。

### 2.2 复现路径

1. 设置页或项目详情页 **全选** 或勾选完整质量子项。
2. 启动 Unity 测试并等待完成。
3. 打开分析页「渲染质量」Tab 或项目内 SessionResultPanel。
4. 展开四大类「主要依据」，观察「暂无数据」子项。

### 2.3 相关近期改动（背景）

- 前端 `RenderQualityPanel` 已改为：按 `test_scope` **展示全部已勾选子项**；`null` 显示「暂无数据」（不再隐藏）。
- 后端 `RenderQualityService.SCOPED_METRIC_BINDINGS` 已按 scope 动态生成 metrics 字典。

上述改动**暴露了**原本被隐藏的数据缺口，并非新问题根因。

---

## 3. 数据流与判定逻辑

```text
[指标选择器 test_scope]
        ↓
[unity_runner execution_plan + qualityMetricChecks]  →  Unity XRTestConfig 细分开关
        ↓
[Unity Collectors 采集]  →  PerformanceSample / renderQuality JSON
        ↓
[batch upload → performance_samples 表 + extra_metrics.render_quality]
        ↓
[RenderQualityService._build_stats + _collect_extra_quality_metrics]
        ↓
[SCOPED_METRIC_BINDINGS 按 scope 取数]  →  category.metrics
        ↓
[前端 buildMetricDisplayItems(includeMissing=true)]  →  null ⇒ 「暂无数据」
```

### 3.1 后端何时得到 `null`

`SCOPED_METRIC_BINDINGS` 中 getter 从 `stats` 取值，例如 `stats.get("peak_active_light_count")`。  
当以下任一情况成立时，结果为 `null`：

1. 样本中**从未出现**该字段的有效值；
2. 样本值全部为 Unity 哨兵 **`-1`**（表示该子项在 Unity 侧未启用采集），被 `_collect_extra_quality_metrics` 的 `value >= 0` 过滤；
3. 字段走 **DB 列**（如 `texture_memory_mb`），但 Unity 上传未填充对应 key；
4. 字段仅存在于 **extra_metrics 布尔 flag**（如 `overexposure`），Unity 从未写入。

### 3.2 与「未测试 / 跳过」的区别

| 维度 | 未测试 / 跳过 | 暂无数据 |
|------|----------------|----------|
| `test_scope` 中是否勾选 | 否 | **是** |
| `category.tested` | `false`（整类）或 section_status=skipped | `true`（大类仍评分） |
| `category.metrics` 是否含该 key | 不含 | **含，值为 null** |
| 评分 | 大类权重为 0 或不参与 | 大类仍参与；缺数可能触发「缺少采集」扣分或静默跳过 |

---

## 4. 根因分类

### 4.1 Unity 侧：配置开关存在，但采集器未实现（P0）

`XRTestConfig` 与 `XRBatchTestRunner` 已为下列子项下发 **qualityMetricChecks** 布尔开关，但 **`RenderQualityCollector` 未实现对应采集**，上传 JSON 中也无字段：

| scope ID | Config 开关 | Unity 实现状态 |
|----------|-------------|----------------|
| `lighting.exposure_artifacts` | `testLightingExposureArtifacts` | ❌ 无采集；无 `exposure_delta` / 过曝欠曝 flag |
| `post_processing.warnings` | `testPostProcessWarnings` | ❌ 无采集；无 `post_processing_warning` flag |
| `physics.penetration` | `testPhysicsPenetration` | ❌ 无采集；无 `penetration_event_count` |
| `physics.pose_latency` | `testPhysicsPoseLatency` | ❌ 无采集；`pose_latency_ms` 未写入样本 |
| `physics.prediction_error` | `testPhysicsPredictionError` | ❌ 无采集；`prediction_error_ms` 未写入样本 |

**影响**：用户勾选后范围横幅计入「已纳入」，结果页显示「暂无数据」；评分中相关扣分条件因 `None` **不触发**（如穿模、姿态延迟），与「已纳入测试」语义矛盾。

**相关文件**：

- `unity-xr-collector/Runtime/Core/XRTestConfig.cs`（开关定义）
- `unity-xr-collector/Editor/XRBatchTestRunner.cs`（任务配置应用）
- `unity-xr-collector/Runtime/Collectors/RenderQualityCollector.cs`（仅实现场景计数类）

---

### 4.2 Unity 侧：依赖其他采集器，但字段未映射上报（P0）

| scope ID | 依赖采集器（catalog） | 问题 |
|----------|----------------------|------|
| `materials.texture_memory` | `memory` | `MemoryCollector` 只写 `graphicsMemoryMB`，**不写** `textureMemoryMB`；后端 batch 用 `graphicsMemoryMB` 回退填入 `texture_memory_mb` 列，**语义是显存而非纹理内存**，且若 GPU/内存未开则仍为空 |
| `post_processing.render_texture_memory` | 无独立采集器 | Unity 上传 **无** `renderTextureMemoryMB`；DB 列 `render_texture_memory_mb` 恒为空 |
| `post_processing.gpu_frame_budget` | `gpu` + `frame_time` | 展示依赖 `avg_gpu`、`p95_frame_ms`；若未开 GPU/帧时间或样本无有效帧时 → 暂无数据 |
| `materials.draw_calls` | `rendering_stats` | 依赖 `drawCalls`；Editor 冷启动无 Camera 渲染时可能长期为 **0**（见 `unity-cold-start.md`），与「暂无数据」不同但易误解 |
| `physics.long_frames` | `frame_time` | 来自 `long_frame_count`（帧时 >33ms 统计）；无帧时间样本时为 0 而非 null |

**相关文件**：

- `unity-xr-collector/Runtime/Collectors/MemoryCollector.cs`
- `unity-xr-collector/Runtime/Network/TestDataUploader.cs` → `AppendPerformanceMetrics`
- `backend/app/routers/data_collection.py`（`graphicsMemoryMB` → `texture_memory_mb` 回退）

---

### 4.3 Unity 侧：`-1` 哨兵与 scope 不一致（P1）

`RenderQualityCollector.ResetMetrics()` 对未启用子项赋 **`-1`**，上传至 `renderQuality.*`。

后端 `_collect_extra_quality_metrics`：

```python
if isinstance(value, (int, float)) and value >= 0:
    values[name].append(float(value))
```

**`-1` 被丢弃**。若网页 scope 启用但 Unity task 未正确传递 `qualityMetricChecks`（域重载覆盖、旧会话 config 等），则全程 `-1` → `peak_*` 不存在 → **暂无数据**。

---

### 4.4 后端：聚合路径不统一（P1）

渲染质量场景计数有两条潜在路径，但 **评分服务只走一条**：

| 数据来源 | 存储位置 | `_build_stats` 是否使用 |
|----------|----------|-------------------------|
| Unity `renderQuality` 对象 | `extra_metrics.render_quality` | ✅ `_collect_extra_quality_metrics` → `peak_*` |
| Unity 样本顶层字段（若将来直写 DB 列） | 无对应列（仅 draw_calls、texture_memory_mb 等） | 部分用于 `avg_draw_calls` 等 |
| `PerformanceSample` 上的 `activeLightCount` 等 | **未落库独立列**，仅在 extra_metrics | 仅走路径 1 |

若 batch 解析未把 `renderQuality` 并入 `extra_metrics`（历史数据、上传格式异常），则**整组 peak 为空**。

**相关文件**：

- `backend/app/services/render_quality_service.py` → `_collect_extra_quality_metrics`、`_build_stats`
- `backend/app/routers/data_collection.py` → batch 样本解析

---

### 4.5 产品 / 评分：三态未在 UI 区分（P1）

当前渲染质量子项只有：

- 有数值
- **暂无数据**（`null`）

缺少明确第三态：

- **已纳入但环境不支持**（`unavailable`）
- **已纳入但采集失败**（`failed` / `pending`）

`TestScopeService.build_section_status` **仅覆盖基础性能 6 项**，质量 21 子项**没有**对应的 `section_status`，导致分析页无法像 FPS 一样显示「跳过 / 不可用」。

评分侧已有部分缺数处理，但不统一：

```python
# 示例：有缺数扣分
score = self._deduct(..., light_count is None, 8, "缺少光源数量采集，评分可信度降低")

# 示例：None 时不扣分（用户以为测了）
score = self._deduct(..., penetration is not None and penetration > 0, 14, "存在穿模/碰撞异常标记")
```

---

## 5. 指标对照表（21 项质量子项）

| scope ID | 中文名 | 典型展示字段 | Unity 采集 | 上报 | 后端聚合 | 常见「暂无数据」原因 |
|----------|--------|--------------|------------|------|----------|----------------------|
| `lighting.active_lights` | 活动光源数量 | `active_light_count` | ✅ RenderQualityCollector | ✅ | ✅ peak | scope/Unity 不一致；无样本 |
| `lighting.realtime_lights` | 实时光源数量 | `realtime_light_count` | ✅ | ✅ | ✅ peak | 同上 |
| `lighting.shadow_casters` | 阴影投射体数量 | `shadow_caster_count` | ✅ | ✅ | ✅ peak | 同上 |
| `lighting.reflection_probes` | 反射探针数量 | `reflection_probe_count` | ✅ | ✅ | ✅ peak | 同上 |
| `lighting.exposure_artifacts` | 曝光异常标记 | `exposure_delta` 等 | ❌ | ❌ | ❌ | **采集器未实现** |
| `materials.material_slots` | 材质槽数量 | `material_count` | ✅ | ✅ | ✅ peak | 少见 |
| `materials.unique_materials` | 去重材质数量 | `unique_material_count` | ✅ | ✅ | ✅ peak | `-1` 过滤；无 metrics 阶段样本 |
| `materials.transparent_materials` | 透明材质数量 | `transparent_material_count` | ✅ | ✅ | ✅ peak | 少见 |
| `materials.draw_calls` | Draw Call | `avg_draw_calls` | ✅ RenderingStats | ✅ 列 | ✅ mean | 冷启动 0；未开 rendering_stats |
| `materials.texture_memory` | 纹理内存 | `peak_texture_memory_mb` | ⚠️ 仅 graphics 回退 | ⚠️ | ⚠️ | **无真实纹理内存字段** |
| `post_processing.volumes` | 后处理 Volume | `post_process_volume_count` | ✅（依赖 URP Volume 类型） | ✅ | ✅ peak | 非 URP 项目恒 0 |
| `post_processing.render_textures` | RenderTexture 数量 | `render_texture_count` | ✅ | ✅ | ✅ peak | 少见 |
| `post_processing.render_texture_memory` | RT 内存 | `peak_render_texture_memory_mb` | ❌ | ❌ | ❌ | **未上报、未采集** |
| `post_processing.gpu_frame_budget` | GPU 帧预算 | `avg_gpu` + `p95_frame_time_ms` | ⚠️ 衍生 | ⚠️ | ⚠️ | 依赖 GPU+帧时；未开则 null |
| `post_processing.warnings` | 后处理警告 | `post_processing_warning_count` | ❌ | ❌ | ⚠️ flag 无写入 | **采集器未实现** |
| `physics.rigidbodies` | 刚体数量 | `rigidbody_count` | ✅ | ✅ | ✅ peak | 少见 |
| `physics.colliders` | 碰撞体数量 | `collider_count` | ✅ | ✅ | ✅ peak | 少见 |
| `physics.penetration` | 穿模/碰撞异常 | `penetration_event_count` | ❌ | ❌ | ❌ | **采集器未实现** |
| `physics.pose_latency` | 姿态延迟 | `avg_pose_latency_ms` | ❌ | ❌ | ❌ | **采集器未实现** |
| `physics.prediction_error` | 预测误差 | `avg_prediction_error_ms` | ❌ | ❌ | ❌ | **采集器未实现** |
| `physics.long_frames` | 物理导致长帧 | `long_frame_count` | ⚠️ 衍生帧时 | ✅ | ✅ 常为 0 | 无帧时数据；0 非「暂无」 |

---

## 6. 对评分系统的影响

### 6.1 当前行为摘要

- **大类未勾选**：`_untested_category`，`tested=false`，权重不计入总分。
- **大类已勾选**：始终 `tested=true`，按规则扣分；缺数时：
  - 部分规则显式扣「缺少采集」分（光照光源、材质数量、后处理 Volume 等）；
  - 部分规则仅在 `value is not None` 时扣分（穿模、姿态延迟、曝光波动等）→ **缺数 = 不扣分 = 虚高**。

### 6.2 风险

1. **用户信任**：勾选「已纳入」但看到「暂无数据」，会认为系统漏测。
2. **分数失真**：未实现采集的子项不参与扣分，整体质量分可能**偏高**。
3. **范围与评分不一致**：`test_scope_summary.selected_count` 含未实现项，但 `evidence.has_runtime_quality_metrics` 仅为粗粒度布尔值，无法按子项反馈。

### 6.3 期望行为（产品规则）

引用 `docs/problems/selectable-test-metrics-plan.md` §2.3：

> 区分「采集项」与「展示/评分项」；用户勾选后却无数据应统一表达，**不能**与值为 0 混淆。

建议统一三态：

| 状态 | 条件 | UI | 评分 |
|------|------|-----|------|
| `skipped` | scope 未勾选 | 不展示或「跳过」 | 不扣分、不计权重 |
| `unavailable` | 已勾选但环境/能力不支持 | 「不可用」+ 原因 | 不扣分或降权，记入 evidence |
| `available` | 有有效样本 | 展示数值 | 正常扣分 |
| `missing` | 已勾选应采集但无数据 | 「采集失败」/「暂无数据」 | 扣「缺少采集」或标记可信度降低 |

---

## 7. 建议修复方案（供 Codex）

### 7.1 Unity：补齐采集与上报（P0）

1. 在 `RenderQualityCollector` 或独立 Collector 中实现：
   - 曝光异常（`exposure_delta`、`overexposure`/`underexposure`/`lighting_flicker` flag）
   - 后处理警告检测
   - 穿模/碰撞异常计数（或接入物理事件回调）
   - XR 姿态延迟 / 预测误差（或标记 Editor 下 `unavailable`）
2. `MemoryCollector` 或新采集器输出：
   - `textureMemoryMB`（纹理专用，非 graphics 回退）
   - `renderTextureMemoryMB`
3. `TestDataUploader.AppendPerformanceMetrics` 与 DB 字段对齐，避免遗漏 key。

### 7.2 后端：统一聚合与质量子项 status（P0）

1. 扩展 `TestScopeService.build_section_status` 或新增 `build_quality_metric_status(session, scope)`：
   - 输入：scope + 样本聚合结果 + Unity `supportMetricIds`
   - 输出：每个 `QUALITY_METRIC_IDS` 的 `selected | skipped | unavailable | missing | available`
2. `RenderQualityService.evaluate_session` 返回：
   - `category.metrics`：仅 `available` 有值；
   - `category.metric_status`：全量子项状态（供前端展示）。
3. 评分规则统一：**已纳入但 missing 的一律走「缺少采集」或降可信度**，避免 `None` 静默跳过。
4. `_collect_extra_quality_metrics`：考虑区分 `-1`（skipped_by_unity）与「无字段」（missing），写入 `evidence`。

### 7.3 前端：展示与评分语义对齐（P1）

1. `RenderQualityPanel`：将「暂无数据」细分为：
   - **未纳入本次测试**（灰，跳过）
   - **暂无数据（采集缺失）**（橙）
   - **当前环境不支持**（灰蓝）
2. 与 `TestScopeBanner`、分析页 `section_status` 共用同一 status 枚举。
3. 卡片脚注展示：`已纳入 X 项 / 有效数据 Y 项 / 缺失 Z 项`。

### 7.4 联调与回归（P1）

| 用例 | 期望 |
|------|------|
| 全选质量子项 + 正常热启动 | 主要依据 ≥ 已实现项均有值；未实现项标 `missing` 或 `unavailable` |
| 仅勾选光照 5 项 | 仅光照类出现对应 5 行；未勾选不出现 |
| 关闭 `materials.draw_calls` | Unity 上传 -1；后端不聚合；UI 应为 skipped 而非暂无数据 |
| 冷启动 Editor | Draw Call / GPU 等特殊项标 `unavailable` 或 0，文档化说明 |
| 缺数评分 | 质量分含「缺少采集」扣分或 `grade` 降可信度 |

---

## 8. 关键代码索引

| 区域 | 路径 |
|------|------|
| 指标目录与采集依赖 | `backend/app/services/test_metric_catalog.py` |
| 范围规范化 / execution_plan | `backend/app/services/test_scope_service.py` |
| Unity 任务与 qualityMetricChecks | `backend/app/services/unity_runner_service.py` |
| 质量评分与 SCOPED_METRIC_BINDINGS | `backend/app/services/render_quality_service.py` |
| 样本 batch 入库 | `backend/app/routers/data_collection.py` |
| Unity 质量采集 | `unity-xr-collector/Runtime/Collectors/RenderQualityCollector.cs` |
| Unity 上传 JSON | `unity-xr-collector/Runtime/Network/TestDataUploader.cs` |
| 结果展示 | `frontend/src/components/RenderQualityPanel/index.tsx` |
| 指标文案 | `frontend/src/lib/renderQualityLabels.ts` |
| 冷启动相关 | `docs/problems/unity-cold-start.md` |
| 指标可配置化计划 | `docs/problems/selectable-test-metrics-plan.md` |

---

## 9. 验收标准

1. 用户勾选的每个质量子项，在结果页均有明确状态（有值 / 跳过 / 不可用 / 采集缺失），**不再仅用模糊的「暂无数据」**。
2. 已实现采集的子项在热启动正常场景下 **100% 有值**（允许真实 0）。
3. 未实现采集的子项在修复前应在 UI 标为「待实现」或 `unavailable`，且**不**计入 `selected_count` 的「有效数据」统计。
4. 评分文档化：缺数时是否扣分、扣多少，与 UI 状态一致。
5. 提供至少 1 条自动化测试：给定 fixture 样本 + scope，断言 `metric_status` 与 `category.metrics` 符合预期。

---

## 10. 附录：Demo 数据 vs 真实采集

`backend/scripts/seed_demo_data.py` 中的演示会话**人为填充**了 `penetration_event_count`、`pose_latency_ms`、`render_texture_memory_mb` 等字段，因此演示数据可能比真实 Unity 上传**更完整**。

排查时请优先使用**真实测试会话**与 Unity 日志中的 `[XRTestManager] 样本 #N` 摘要对照，避免被 seed 数据误导。
