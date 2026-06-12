# 测试指标可配置化实施方案

> 依据：`docs/problems/selectable-test-metrics-plan.md`  
> 目标：在不破坏现有冷启动、热启动、实时进度、结果上传和历史会话展示的前提下，实现全局默认指标、单次测试选择、按范围分析和统一跳过态。  
> 文档用途：供 Cursor 按阶段实施。  
> 编写日期：2026-06-12

---

## 1. 实施结论

该计划合理，但不应直接从前端 Checkbox 开始改。现有系统已经存在三套配置：

- 前后端启动配置：`metric_checks`、`quality_checks`、`quality_metric_checks`
- Unity 运行配置：`collectFrameRate`、`collectCpuUsage`、`testLightingActiveLights` 等布尔字段
- 结果与历史展示：`TestSession.config`、`TestTask.config`、样本字段和质量评分结果

如果各页面分别判断 Checkbox，很容易出现以下回归：

- 未选择的指标仍以 `0` 上传，被误认为真实采集值；
- 修改全局默认后，历史会话的测试范围跟着变化；
- 关闭 GPU 后，已选择的 Draw Calls 或 GPU 帧预算指标无法采集；
- 关闭某个质量细分项后，后端仍因“缺少数据”扣分；
- 冷启动或 Unity 域重载后丢失选择配置；
- 新前端对旧后端、旧 Unity 插件不兼容。

因此建议采用以下总体路线：

1. **后端建立统一的测试范围规范化层，作为唯一业务判断入口。**
2. **保留现有三个启动字段，新增版本化 `test_scope` 快照，不直接替换旧结构。**
3. **将“用户选择范围”和“Unity 实际执行依赖”分开。**
4. **展示、分析以会话快照为准，不以数值是否为 0 判断是否跳过。**
5. **分阶段上线，每个阶段都保持现有默认行为为“全部启用”。**

---

## 2. 当前代码现状与实施风险

### 2.1 已具备的基础

- 后端启动 API 已接收：
  - `metric_checks`
  - `quality_checks`
  - `quality_metric_checks`
- `UnityRunnerService` 已将这些字段写入 `TestSession.config` 和 `TestTask.config`。
- Unity `XRTestConfig` 已有基础指标、质量大类和质量细分项布尔字段。
- `RenderQualityCollector` 已使用 `-1` 表示部分未启用质量指标。
- `RenderQualityService` 已能将未启用的质量大类输出为“未测试”。
- 前端已有设置页、测试配置页、实时面板、结果面板和分析页。
- 历史会话可从 `session.config` 读取运行时快照。

### 2.2 必须优先解决的风险

#### 风险 A：`0` 不能表示跳过

当前 `PerformanceSample` 的 Unity 字段多为不可空的 `float/int`，未采集时通常仍是 `0`。实时进度 payload 也给所有字段默认值 `0`。

必须遵守：

- 未选择：由 `test_scope` 判断，显示“跳过”；
- 已选择且值为 `0`：显示真实的 `0`；
- 已选择但没有数据：显示“采集不可用”或“暂无数据”；
- 禁止继续使用 `value > 0` 判断是否测试。

#### 风险 B：用户范围与采集依赖不完全一致

例如：

- `materials.draw_calls` 需要 `RenderingStatsCollector`，不应依赖用户是否选择 `gpu`；
- `post_processing.gpu_frame_budget` 需要 GPU 和帧时间数据；
- `physics.long_frames` 需要帧时间；
- `materials.texture_memory`、`post_processing.render_texture_memory` 需要内存或对应资源统计；
- 设备信息仅用于展示，不应被质量大类父级错误关闭。

因此需要区分：

- `requested_scope`：用户明确选择的测试范围，用于展示和评分；
- `execution_plan`：后端根据依赖解析后交给 Unity 的采集计划；
- 支撑指标可以内部采集，但不得作为用户未选择项展示或评分。

#### 风险 C：旧会话没有完整范围

旧会话可能：

- 有三个旧配置字段；
- 只有 `quality_checks`；
- 完全没有指标范围字段。

历史回放必须使用固定回退规则，不能读取当前全局默认。

#### 风险 D：当前分析仍默认计算全部指标

`PerformanceAnalysisService`、阈值检测和 `RenderQualityService` 当前主要按“数据库是否有值”分析。未选择项若上传为 `0`，仍可能参与统计或扣分。

#### 风险 E：分析页仍有演示数据回退

`frontend/src/pages/Analysis/index.tsx` 在缺少真实结果时仍会显示部分固定演示值。实施跳过态时必须移除这类回退，否则未测试指标仍会显示看似正常的数据。

---

## 3. 统一数据模型

### 3.1 新增版本化 `test_scope`

在保持旧字段不变的基础上，为系统默认、启动请求、任务配置和会话配置增加统一快照：

```json
{
  "test_scope": {
    "schema_version": 1,
    "source": "single_run_override",
    "basic_metrics": {
      "frame_rate": true,
      "frame_time": true,
      "cpu": true,
      "gpu": true,
      "memory": true,
      "device_info": true
    },
    "quality_categories": {
      "lighting": true,
      "materials": true,
      "post_processing": true,
      "physics": true
    },
    "quality_metrics": {
      "lighting.active_lights": true,
      "lighting.realtime_lights": true,
      "lighting.shadow_casters": true,
      "lighting.reflection_probes": true,
      "lighting.exposure_artifacts": true,
      "materials.material_slots": true,
      "materials.unique_materials": true,
      "materials.transparent_materials": true,
      "materials.draw_calls": true,
      "materials.texture_memory": true,
      "post_processing.volumes": true,
      "post_processing.render_textures": true,
      "post_processing.render_texture_memory": true,
      "post_processing.gpu_frame_budget": true,
      "post_processing.warnings": true,
      "physics.rigidbodies": true,
      "physics.colliders": true,
      "physics.penetration": true,
      "physics.pose_latency": true,
      "physics.prediction_error": true,
      "physics.long_frames": true
    }
  }
}
```

规则：

- 所有已知 key 必须完整存在，禁止只存“选中的 key”。
- `schema_version` 用于以后增加指标时兼容历史会话。
- `source` 可使用：
  - `built_in_default`
  - `global_default`
  - `single_run_override`
  - `legacy_inferred`
- `test_scope` 是用户可见的测试范围，不包含内部依赖采集项。

### 3.2 保留现有字段

在第一版中继续写入：

```json
{
  "metric_checks": {},
  "quality_checks": {},
  "quality_metric_checks": {}
}
```

原因：

- 当前 Unity 启动、日志和后端评分已经依赖这些字段；
- 避免一次性修改所有消费者；
- 允许旧前端或旧任务配置继续工作。

这三个字段应由后端根据规范化后的 `test_scope` 生成，不再由各调用方自行拼装。

### 3.3 新增内部 `execution_plan`

后端启动 Unity 前解析依赖，生成仅供执行使用的计划：

```json
{
  "execution_plan": {
    "schema_version": 1,
    "collector_flags": {
      "frame_rate": true,
      "frame_time": true,
      "cpu": true,
      "gpu": true,
      "memory": true,
      "device_info": true,
      "rendering_stats": true,
      "render_quality": true
    },
    "support_metric_ids": [
      "frame_time",
      "gpu"
    ]
  }
}
```

`support_metric_ids` 表示因依赖而内部采集、但用户未选择的指标。它们：

- 可以供已选择的质量规则计算；
- 不显示为本次用户测试项；
- 不参与无关统计、阈值和报告展示。

### 3.4 状态语义

前端和后端统一使用以下语义：

| 状态 | 含义 | 展示 |
|------|------|------|
| `selected` | 用户选择且有数据 | 正常显示 |
| `skipped` | 用户未选择 | 灰色“跳过 / 未纳入本次测试” |
| `unavailable` | 用户选择，但运行环境或采集器未提供数据 | 橙色“采集不可用” |
| `pending` | 测试尚未开始或暂未收到数据 | “等待采集” |

不要通过改变数据库数值来表达这些状态。范围来自 `test_scope`，数据可用性来自样本和分析结果。

---

## 4. 指标目录设计

### 4.1 后端作为权威目录

建议新增：

```text
backend/app/services/test_metric_catalog.py
backend/app/services/test_scope_service.py
```

职责：

- 定义稳定 ID、中文名、分组、默认值、父级、能力类型和依赖；
- 校验未知 key；
- 补齐缺失 key；
- 处理父子关系；
- 从旧配置推断 `test_scope`；
- 生成旧三字段；
- 生成 Unity `execution_plan`；
- 输出前端可消费的指标目录。

目录项建议结构：

```python
{
    "id": "materials.draw_calls",
    "label": "Draw Call",
    "group": "quality_metric",
    "parent_id": "materials",
    "default_enabled": True,
    "capability": "collect_and_analyze",
    "requires_collectors": ["rendering_stats"],
    "requires_metrics": [],
}
```

### 4.2 前端目录策略

推荐新增：

```text
frontend/src/lib/metricsCatalog.ts
frontend/src/lib/testScope.ts
```

前端可保留静态类型和内置 fallback，但运行时目录建议由后端提供：

```http
GET /api/v1/system-settings/test-metrics/catalog
```

这样中文名称、父子关系和默认值由后端统一维护。前端 fallback 仅用于接口不可用时保证页面可打开。

Unity 不需要理解完整目录，只接收后端解析后的布尔字段和执行计划，避免在 Python、TypeScript、C# 三处复制复杂依赖规则。

### 4.3 父子规则

- 父级关闭时，所有子项的**有效值**强制为 `false`。
- 父级重新开启时，建议恢复用户上次选择的子项；若没有历史选择，则使用全局默认。
- 父级开启但所有子项关闭时：
  - UI 应显示“该大类未选择任何细分指标”；
  - 该大类有效范围视为未测试；
  - 后端规范化后可将父级也设为 `false`，避免空分类参与评分。
- 至少一个有效叶子指标开启，否则禁止启动和保存为默认。

---

## 5. 后端实施方案

### 5.1 第一阶段：规范化服务与兼容层

新增 `TestScopeService`，至少提供：

```python
get_builtin_default_scope()
normalize_scope(raw_scope, legacy_fields=None)
infer_scope_from_session_config(config)
validate_scope(scope)
resolve_execution_plan(scope)
to_legacy_fields(scope)
build_scope_summary(scope)
```

规范化优先级：

1. 请求或会话中存在合法 `test_scope`：使用它；
2. 否则从 `metric_checks / quality_checks / quality_metric_checks` 推断；
3. 否则按旧版本行为推断为全部开启，并标记 `source=legacy_inferred`；
4. 永远不能使用当前全局默认解释历史会话。

兼容规则：

- 请求缺少 `metric_checks` 时，维持当前全部开启行为；
- `quality_metric_checks` 为空时，维持当前细分项全部开启行为；
- 未知 key 第一阶段记录 warning 并忽略，后续可改为严格校验；
- API 响应继续保留旧字段。

### 5.2 系统设置接口

不要扩展现有 `/system-settings/unity` 请求体来保存指标，避免保存指标时意外覆盖 Unity 路径。

新增独立接口：

```http
GET /api/v1/system-settings/test-metrics/catalog
GET /api/v1/system-settings/test-metrics
PUT /api/v1/system-settings/test-metrics
POST /api/v1/system-settings/test-metrics/reset
```

`runtime/system_settings.json` 建议结构：

```json
{
  "unity": {
    "unity_executable_path": "",
    "unity_project_path": "",
    "unity_scene_path": "",
    "collector_package_path": ""
  },
  "test_metrics": {
    "default_scope": {
      "schema_version": 1,
      "basic_metrics": {},
      "quality_categories": {},
      "quality_metrics": {}
    }
  }
}
```

要求：

- 更新 Unity 设置时保留 `test_metrics`；
- 更新指标设置时保留 `unity`；
- 文件缺失或字段损坏时回退内置全部开启默认；
- 保存前执行父子归一化和“至少一个叶子项”校验；
- 审计日志记录变更前后的启用指标摘要，不需要记录整份目录。

### 5.3 启动 API

建议在 `UnityTestStartRequest` 中新增可选字段：

```python
test_scope: TestScope | None = None
```

同时继续接收旧三个字段。

启动流程调整为：

```text
接收请求
→ TestScopeService.normalize_scope()
→ validate_scope()
→ resolve_execution_plan()
→ 生成旧三字段
→ 写入 TestSession.config 和 TestTask.config 完整快照
→ 生成 Unity task json
```

`TestSession.config` 和 `TestTask.config` 至少保存：

```json
{
  "test_scope": {},
  "metric_checks": {},
  "quality_checks": {},
  "quality_metric_checks": {},
  "execution_plan": {},
  "test_scope_summary": {
    "selected_ids": [],
    "skipped_ids": []
  }
}
```

注意：

- 快照必须在创建会话时写入，不能等 Unity 上传后补写；
- 冷启动、热启动必须读取同一份 task json；
- 停止测试、查看结果和历史回放不能重新读取全局默认。

### 5.4 分析与评分

### 基础性能分析

`PerformanceAnalysisService` 应先读取会话 `test_scope`：

- FPS 未选择：`fps_analysis` 保持现有字段兼容，但新增状态为 `skipped`；
- 帧时间未选择：稳定性中的 P95/P99、长帧、掉帧率标记为跳过；
- 内存未选择：`memory_analysis` 标记为跳过；
- CPU/GPU 未选择：资源摘要不分析对应字段；
- 阈值规则只对本次选择范围内的指标执行。

建议在 `full-report` 新增，不删除原字段：

```json
{
  "test_scope": {},
  "section_status": {
    "fps": "selected",
    "frame_time": "selected",
    "cpu": "skipped",
    "gpu": "selected",
    "memory": "unavailable",
    "device_info": "selected"
  }
}
```

### 渲染质量评分

当前评分器按大类启用，但细分指标关闭后，仍可能因缺少数据扣分。必须改成规则级依赖：

```python
RULE = {
    "id": "lighting.high_active_lights",
    "requires_scope": ["lighting.active_lights"],
    "requires_data": ["peak_active_light_count"],
}
```

规则执行原则：

- 细分指标未选择：该规则跳过，不扣分；
- 已选择但无数据：标记 `unavailable`，降低“数据完整度”，不应直接当作业务风险扣分；
- 已选择且有数据：正常参与评分；
- 大类没有任何有效细分指标：整个大类输出“未测试”；
- 总分只按实际已测试大类重新归一化权重。

建议在质量结果中增加：

```json
{
  "enabled_metric_ids": [],
  "skipped_metric_ids": [],
  "unavailable_metric_ids": [],
  "data_completeness": 0.85
}
```

### 5.5 进度接口

实时进度不能依靠 `0` 判断跳过。建议给 progress payload 增加可选字段：

```json
{
  "test_scope_version": 1,
  "selected_metric_ids": [],
  "unavailable_metric_ids": []
}
```

为控制每秒 payload 体积，也可以只在后端收到进度后，从 `TestTask.config.test_scope` 合并这些字段再广播，不要求 Unity 每秒重复发送完整范围。

优先推荐后端合并方式：

```text
Unity 上报实时数值
→ progress_ws 查询 task.config.test_scope
→ 广播时附加 test_scope_summary
```

这样旧 Unity 插件仍可工作。

### 5.6 报告导出

`ReportGenerationService` 应新增：

- “本次测试范围”区块；
- “已跳过指标”区块；
- 对跳过的分析章节显示“未纳入本次测试”；
- 不输出演示值或把缺失值渲染成 `0`；
- 报告摘要中的平均 FPS、质量分等字段若跳过，应为 `None`。

---

## 6. Unity 插件实施方案

### 6.1 保持启动配置兼容

第一版继续使用现有 task json 字段：

```text
collectFrameRate
collectFrameTime
collectCpuUsage
collectGpuUsage
collectMemory
collectDeviceInfo
qualityChecks
qualityMetricChecks
```

可新增可选字段：

```text
testScopeVersion
requestedMetricIds
supportMetricIds
collectRenderingStats
collectRenderQuality
```

旧 task json 缺少新字段时，必须保持当前全部开启默认。

### 6.2 采集器依赖解析

依赖解析主要由后端完成，Unity 只根据解析结果启停采集器。

必须拆开当前隐式绑定：

- `GpuUsageCollector` 只负责 GPU；
- `RenderingStatsCollector` 由 `collectRenderingStats` 控制；
- `RenderQualityCollector` 由 `collectRenderQuality` 和细分开关控制；
- 不要继续无条件将 `RenderingStatsCollector` 和 `RenderQualityCollector` 加入全部采集列表。

推荐依赖表：

| 用户选择项 | Unity 必需采集器 |
|------------|------------------|
| `frame_rate` | `FrameRateCollector` |
| `frame_time` | `FrameTimeCollector` |
| `cpu` | `CpuUsageCollector` |
| `gpu` | `GpuUsageCollector` |
| `memory` | `MemoryCollector` |
| `device_info` | `DeviceInfoCollector` |
| `materials.draw_calls` | `RenderingStatsCollector` |
| `materials.texture_memory` | `MemoryCollector` / 对应纹理统计 |
| `post_processing.gpu_frame_budget` | `GpuUsageCollector` + `FrameTimeCollector` |
| `physics.long_frames` | `FrameTimeCollector` |
| 质量场景计数类 | `RenderQualityCollector` |

### 6.3 样本上传策略

短期兼容方案：

- 保持现有样本 JSON 字段；
- 后端根据 `test_scope` 决定是否分析和展示；
- 质量细分项继续使用 `-1` 表示未启用，后端过滤 `-1`。

后续优化方案：

- 上传器对未选择字段省略 JSON key，使数据库存储为 `NULL`；
- 不要使用 `0` 或 `-1` 作为所有指标的统一跳过标记；
- 该优化应在范围语义上线稳定后再做，避免同时修改上传格式与展示逻辑。

### 6.4 冷启动与热启动可靠性

新配置必须沿用现有可靠链路：

- task json 是冷启动和热启动的共同来源；
- `SessionState` 中保存完整 task json，域重载后重新应用；
- 不新增依赖场景序列化值的配置来源；
- `XRBatchTestRunner.ApplyTaskConfig()` 必须应用所有新增执行字段；
- 日志输出用户范围和内部支撑采集项，便于定位依赖行为：

```text
[XRBatchTestRunner] 用户选择：FPS、Draw Calls
[XRBatchTestRunner] 内部支撑采集：RenderingStats
```

---

## 7. 前端实施方案

### 7.1 公共类型与工具

建议新增：

```text
frontend/src/lib/metricsCatalog.ts
frontend/src/lib/testScope.ts
frontend/src/components/MetricScopeSelector/
frontend/src/components/TestScopeBanner/
frontend/src/components/MetricSkippedPlaceholder/
frontend/src/components/MetricUnavailablePlaceholder/
```

`testScope.ts` 负责：

- 从后端目录构建默认 scope；
- 处理父子 Checkbox；
- 计算已选择和已跳过摘要；
- 从历史 `session.config` 读取 `test_scope`；
- 对旧会话执行固定 legacy 推断；
- 判断指定指标状态。

禁止在 `ProjectDetail`、`SessionResultPanel`、`Analysis` 中各自实现一套 scope 推断。

### 7.2 设置页

将设置页拆为 Tabs：

1. `Unity 本地测试路径`
2. `测试指标`

两个 Tab 使用独立 Form 和独立保存按钮：

- 路径 Tab 继续调用 `/system-settings/unity`；
- 指标 Tab 调用 `/system-settings/test-metrics`；
- 保存其中一个 Tab 不得提交或覆盖另一个 Tab 的数据。

指标选择器建议：

- 基础性能指标单独一组；
- 质量大类使用可折叠 Card；
- 父级 Checkbox 支持 `checked / indeterminate / unchecked`；
- 子项展示简短说明和依赖提示；
- 提供“全部选择”“恢复系统默认”；
- 全不选时禁用保存并显示明确错误。

### 7.3 项目详情测试配置

加载顺序：

```text
加载引擎、场景、指标目录、全局默认
→ 使用全局默认初始化 Form
→ 用户单次修改
→ 提交完整 test_scope
```

要求：

- 不再只提交 4 个质量大类；
- 提交完整布尔快照，而不是仅提交已选 key；
- 单次修改不写回全局默认；
- “再次开始测试”默认建议使用全局默认；如产品需要复用上次范围，应提供明确按钮，不要隐式复用；
- 启动前执行至少一个有效叶子项校验；
- 可显示“本次将测试 N 项，跳过 M 项”。

### 7.4 实时监控页

`ActiveUnityRun` 增加从 `session.config.test_scope` 读取的范围快照。

页面顶部显示 `TestScopeBanner`：

```text
本次测试范围：FPS、帧时间、CPU、光照与阴影……
已跳过：GPU、设备信息……
```

指标卡规则：

- 未选择：显示灰色“跳过”，不要显示 `0`；
- 已选择但尚无进度：显示“等待采集”；
- 已选择且数据不可用：显示“采集不可用”；
- 已选择且数值为 0：正常显示 `0`。

运行详情中的质量细分项同样按 scope 判断。不要隐藏整块区域，否则用户无法区分“页面没有此能力”和“本次跳过”。

### 7.5 结果面板与分析页

所有页面从 `fullReport.test_scope` 或 `session_info.config.test_scope` 获取范围。

建议规则：

- 保留现有 Tab 顺序，避免界面结构大幅变化；
- 未选择的 Tab 内容显示统一跳过占位；
- 部分选择的资源 Tab 只画已选择曲线；
- FPS、帧时间等顶部 Statistic 未选择时显示“跳过”，不能显示 `0`；
- `device_info` 未选择时，设备信息页显示跳过；
- 渲染质量大类和细分指标分别显示未测试状态；
- 移除 `Analysis/index.tsx` 中缺少真实数据时显示演示值的逻辑。

### 7.6 历史会话

历史页面只读取会话快照：

```text
session.config.test_scope
→ 若不存在，使用 legacy 推断
→ 永远不读取当前全局默认
```

对于完全没有范围信息的旧会话，顶部应附加提示：

> 该会话由旧版本创建，测试范围按旧版本“全部启用”规则推断。

---

## 8. 分阶段实施顺序

每一阶段完成后都应可独立上线，且保持默认全部开启时与当前行为一致。

### 阶段 0：建立基线

在修改功能前完成：

- 后端全量测试通过；
- 前端 `check`、`lint`、`build` 通过；
- 记录一次冷启动、热启动的 task json、session config、实时 progress 和 full report；
- 保留当前全部指标测试作为回归样本。

### 阶段 1：后端规范化与系统默认

实施：

- 指标目录；
- `TestScopeService`；
- 测试指标设置 API；
- 系统设置文件扩展；
- legacy 推断；
- 单元测试。

此阶段不要修改 Unity 采集逻辑，默认行为必须完全不变。

验收：

- 未配置指标设置时仍全部开启；
- 更新指标设置不影响 Unity 路径；
- 更新 Unity 路径不影响指标设置；
- 旧会话可推断固定范围。

### 阶段 2：启动快照与前端选择器

实施：

- 启动请求支持 `test_scope`；
- 后端规范化后写入任务和会话快照；
- 设置页 Tabs；
- 测试页完整选择器；
- 至少一个叶子项校验。

此阶段 Unity 仍可按旧布尔字段执行，避免同时改动过多。

验收：

- 全局默认正确初始化单次测试；
- 单次覆盖不改变全局默认；
- task/session config 保存完整快照；
- 冷启动和热启动 task json 一致。

### 阶段 3：统一跳过展示与范围感知分析

实施：

- `TestScopeBanner`；
- 跳过/不可用公共组件；
- 实时监控按范围显示；
- 结果与分析页按范围显示；
- full report 增加 `test_scope` 和 `section_status`；
- 阈值、基础分析和质量评分按范围裁剪；
- 报告导出标注范围。

验收：

- 未选指标不显示假 `0`；
- 已选且真实为 `0` 时显示 `0`；
- 已选但无数据时显示“采集不可用”；
- 历史会话不受全局默认变化影响；
- 关闭质量细分项不会因“缺少数据”被扣分。

### 阶段 4：Unity 真正裁剪采集

实施：

- 后端生成 `execution_plan`；
- Unity 拆分 GPU、RenderingStats、RenderQuality 开关；
- 按依赖启停采集器；
- 日志输出用户范围与内部支撑项；
- 可选地省略未选择样本字段。

验收：

- 仅选择 Draw Calls 时仍能采集 Draw Calls，不要求用户同时选择 GPU；
- 仅选择 GPU 帧预算时内部自动采集 GPU 和帧时间，但界面只显示用户选择范围；
- 冷启动、热启动和域重载后范围不丢失；
- 停止与上传流程无回归。

### 阶段 5：报告与扩展指标

实施：

- 参考帧、热管理、阈值等能力纳入目录；
- 报告导出完整标注跳过项；
- 按需要增加 schema version 迁移。

---

## 9. 测试方案

### 9.1 后端单元测试

至少覆盖：

- 内置默认包含全部已知 key；
- 缺失字段回退为当前全部开启行为；
- 父级关闭强制关闭子项；
- 父级开启但无子项时规范化正确；
- 全不选被拒绝；
- 未知 key 的处理符合约定；
- 更新路径设置保留指标设置；
- 更新指标设置保留路径设置；
- 启动请求写入完整 `test_scope` 和旧字段；
- legacy 会话固定推断，不读取全局默认；
- 阈值不处理跳过指标；
- 质量细分项跳过时不扣分；
- 已选择但无数据时返回 `unavailable`；
- 合法 `0` 仍被当作真实数据。

### 9.2 前端测试

至少覆盖：

- 选择器父子联动和半选状态；
- 全局默认初始化；
- 单次覆盖不修改默认；
- 全不选时禁止启动；
- 跳过、不可用、真实 `0` 三种状态；
- 历史会话使用快照；
- legacy 会话提示；
- 资源图表只渲染已选择曲线；
- 设备信息未选择时显示跳过。

若项目暂未配置前端测试框架，至少将纯逻辑集中到 `testScope.ts`，便于后续补充单元测试，避免把核心判断埋在 JSX 中。

### 9.3 端到端测试矩阵

| 场景 | 预期 |
|------|------|
| 默认全部开启，冷启动 | 行为与当前版本一致，全部数据正常 |
| 默认全部开启，热启动 | 行为与当前版本一致，范围不丢失 |
| 仅 FPS | 仅 FPS 展示；其他项显示跳过 |
| 仅 CPU + 内存 | FPS/帧时间显示跳过；CPU/内存正常 |
| 仅 Draw Calls | 内部启用 RenderingStats；Draw Calls 正常 |
| 仅质量大类的部分细分项 | 只分析已选规则，未选规则不扣分 |
| 已选指标返回真实 0 | 显示 0，不显示跳过 |
| 已选指标无数据 | 显示采集不可用 |
| 测试中手动停止 | 范围快照保留，会话正确取消 |
| 修改全局默认后查看旧会话 | 旧会话范围不变化 |
| 旧版本历史会话 | 按 legacy 规则展示并提示 |

---

## 10. 关键文件改动清单

### 后端

```text
backend/app/services/test_metric_catalog.py              # 新增
backend/app/services/test_scope_service.py                # 新增
backend/app/services/system_settings_service.py
backend/app/routers/system_settings.py
backend/app/routers/unity_runner.py
backend/app/services/unity_runner_service.py
backend/app/routers/progress_ws.py
backend/app/services/performance_analysis_service.py
backend/app/services/render_quality_service.py
backend/app/services/report_generation_service.py
backend/tests/test_system_settings.py
backend/tests/test_test_scope.py                          # 新增
backend/tests/test_unity_runner_scope.py                  # 新增
backend/tests/test_analysis_scope.py                      # 新增
```

### 前端

```text
frontend/src/api/systemSettings.ts
frontend/src/api/unityRunner.ts
frontend/src/api/analysis.ts
frontend/src/lib/metricsCatalog.ts                        # 新增
frontend/src/lib/testScope.ts                             # 新增
frontend/src/components/MetricScopeSelector/              # 新增
frontend/src/components/TestScopeBanner/                  # 新增
frontend/src/components/MetricSkippedPlaceholder/         # 新增
frontend/src/components/MetricUnavailablePlaceholder/     # 新增
frontend/src/pages/Settings/index.tsx
frontend/src/pages/Projects/ProjectDetail.tsx
frontend/src/components/SessionResultPanel/index.tsx
frontend/src/components/RenderQualityPanel/index.tsx
frontend/src/components/SessionDeviceInfoPanel/index.tsx
frontend/src/pages/Analysis/index.tsx
```

### Unity

```text
unity-xr-collector/Editor/XRBatchTestRunner.cs
unity-xr-collector/Runtime/Core/XRTestConfig.cs
unity-xr-collector/Runtime/Core/XRTestManager.cs
unity-xr-collector/Runtime/Network/UnityProgressReporter.cs
unity-xr-collector/Runtime/Network/TestDataUploader.cs
unity-xr-collector/Runtime/Collectors/RenderQualityCollector.cs
unity-xr-collector/Runtime/Collectors/RenderingStatsCollector.cs
```

---

## 11. 明确禁止的实施方式

- 不要删除或一次性替换现有三个配置字段。
- 不要根据数值为 `0` 判断指标被跳过。
- 不要让历史会话读取当前全局默认。
- 不要在每个前端页面单独实现范围推断。
- 不要将 GPU、Draw Calls 和全部渲染质量指标继续视为同一个开关。
- 不要因已选择指标采集失败而自动显示为“跳过”。
- 不要因细分指标未选择而在评分中按“缺少证据”扣分。
- 不要在第一阶段同时重构上传 JSON、数据库结构和全部 UI。
- 不要改变当前冷启动与热启动任务配置来源。
- 不要在分析页使用演示数据代替未测试或缺失数据。

---

## 12. Cursor 执行检查单

建议 Cursor 每完成一个阶段后逐项确认：

- [ ] 默认全部开启时，现有功能和数据结果无回归
- [ ] 新旧启动请求均可工作
- [ ] `TestSession.config` 和 `TestTask.config` 含完整范围快照
- [ ] 全局默认与单次覆盖互不污染
- [ ] 历史会话只读取自身快照
- [ ] 跳过、不可用、真实 0 可明确区分
- [ ] 父子范围被后端统一规范化
- [ ] 采集器依赖由 `execution_plan` 解析
- [ ] 质量评分只使用已选择细分项
- [ ] 阈值只检查已选择指标
- [ ] 冷启动、热启动、停止、上传流程通过
- [ ] 后端测试通过
- [ ] 前端 `npm run check && npm run lint && npm run build` 通过
- [ ] Unity 实际编译通过
- [ ] 至少完成一次冷启动和一次热启动端到端验证

---

## 13. 最终验收定义

只有同时满足以下条件，才算完成该计划：

1. 管理员可以保存全局默认测试范围；
2. 用户可以在单次测试前覆盖范围；
3. 每次任务和会话保存不可变的范围快照；
4. Unity 根据解析后的执行计划采集必要数据；
5. 后端只分析和评分用户选择的范围；
6. 前端所有入口统一区分跳过、不可用和真实 `0`；
7. 历史会话不受全局设置变化影响；
8. 默认全部开启时与当前系统行为兼容；
9. 冷启动、热启动、停止、实时进度、上传和报告导出均无回归。
