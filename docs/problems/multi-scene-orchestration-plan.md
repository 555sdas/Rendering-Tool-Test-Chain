# 多场景连续测试编排（Problem Document）

> 文档用途：描述「一次性标记多个场景、按编排顺序连续测试、每场景独立配置指标」的需求背景、现状约束与待决策问题，供 Codex 在此基础上输出实现方案。  
> 最后更新：2026-06-12  
> 状态：**产品决策已确认，待 Codex 输出实现方案**

---

## 1. 背景与目标

### 1.1 现状

当前 Unity 本地测试链路是**严格的单场景模型**：

- 项目详情页「Unity 本地测试」仅允许选择 **1 个** `scene_resource_id`；
- 每次点击「启动 Unity 测试」创建 **1 个 TestTask + 1 个 TestSession**，二者绑定同一个 `scene_id`；
- Unity 插件 `XRBatchTestRunner.OpenConfiguredScene()` 使用 `OpenSceneMode.Single`，每次运行只打开一个场景；
- 测试指标（`test_scope`）在启动前全局配置一份，**所有场景共用**，无法在编排中为不同场景单独裁剪；
- 前端仅维护一个 `activeRun` 状态，监控面板展示单场景进度；
- 会话命名 `#N` 按**平台项目**递增，与「批量编排」无关联。

因此，用户若要对同一 Unity 工程下多个场景做回归，只能**手动重复启动 N 次**，无法一次性提交编排计划。

### 1.2 目标

新增**多场景连续测试（Multi-Scene Orchestration）**能力：

1. 用户可一次性**勾选/排序多个场景**，形成测试编排（Playbook / Run Plan）；
2. 系统按编排顺序**自动连续执行**各场景测试，无需人工逐次点击启动；
3. **每个场景可单独编辑**需要测试的指标（`test_scope`），支持继承全局默认后逐场景覆盖；
4. 提供**合理、可操作的 UI**：编排列表、顺序调整、逐场景指标编辑、运行中进度、历史结果查看；
5. 与现有单场景测试、可选指标、报表导出、热/冷启动等能力**兼容共存**。

本文档只描述问题、约束与开放议题，**不包含具体实施步骤**；实现方案由 Codex 在此基础上展开。

---

## 2. 产品决策（已确认，2026-06-12）

> 以下由产品负责人确认，Codex 写方案时**默认采纳**，无需再作为开放题讨论。

| ID | 决策项 | 结论 |
|----|--------|------|
| **Q1** | 默认入口与模式切换 | **默认单场景**。UI 提供「多场景」按钮；点击后界面切换为多场景编排模式，支持**添加、删除、调整场景顺序**。再切回即恢复单场景表单。 |
| **Q2** | Unity 工程范围 | **首版仅支持同一 Unity 项目下的多个场景**。不允许跨不同 `unity_project_path` 混合编排。 |
| **Q3** | Unity 执行方式 | **优先同 Editor 连续换场景**（一次启动 / 热启动投递后，在进程内按顺序 `OpenScene` → 采集 → 上传 → 下一场景）。非首版目标：每场景冷启动新进程。 |
| **Q4** | 会话与历史展示 | **每个场景对应独立 Session**（独立分析数据）。列表层增加**运行类型标记**：`单场景` / `多场景`。单场景列表与交互**保持现状**；多场景在详情/结果区用 **Tab 栏切换各场景数据**，单场景 Tab 内 UI 可复用现有 `SessionResultPanel` / 分析组件。 |
| **Q5** | 编排持久化 | **首版不做**当次编排的保存/加载/命名模板。后续可能在**设置页**增加「全局场景编排」配置（本期不实施）。 |
| **Q6** | 场景失败处理 | **不自动继续、不自动终止**。某场景失败时**向用户发送明确提示**（页面通知 + 编排监控区），由用户决定：**重试当前场景 / 跳过并继续下一个 / 终止整批**。 |
| **Q7** | 采集参数粒度 | **`test_scope`、采集间隔、帧率/指标采集时长等均按场景独立配置**（per-scene），不设编排级统一覆盖（引擎、`batchmode`、`ensure_plugin` 仍可编排级全局，见 §3.1）。 |

### 2.1 决策摘要（一段话）

单场景为默认体验；用户通过按钮进入多场景模式，在同一 Unity 工程内编排多个场景的顺序与 per-scene 指标/时长，由同一 Editor 连续执行。每场生成独立 Session，列表用标签区分单/多场景，多场景结果用 Tab 切换查看。失败时暂停并交由用户选择；不做编排模板持久化。

### 2.3 会话展示命名（Q9，已确认 2026-06-12）

- **列表与详情主标签直接显示场景名**（如 `Lobby`、`Battle`），来源于 `scene_resource_name` / `unity_scene_path` 解析；
- 会话序号 `#N` 保留为次要信息（技术标识），不作为主展示名；
- 多场景批次：各场景独立 Session，**每个 Session 的「测试场景」标签即该场景名**；批次内用 Tab 切换时 Tab 标题也用场景名；
- 不采用 `#12-1 Lobby` 这类复合命名作为主显示。

### 2.4 仍待补充确认（非阻塞）

| ID | 问题 | 说明 |
|----|------|------|
| Q8 | 场景级备注字段 | 未确认是否需要（如负责人、预期 FPS） |
| Q10 | 新加场景默认指标 | 建议继承设置页全局 `default_scope`，待方案写明默认值 |

---

## 3. 用户场景（User Stories）

| # | 场景 | 期望 |
|---|------|------|
| U1 | 美术/TA 对 Demo 工程 5 个关卡场景做夜间回归 | 一次提交 5 场景编排，睡前启动，次日查看各场景报告 |
| U2 | 性能同学对比「大厅 / 战斗 / 过场」三场景 | 三场景指标范围不同：大厅全开，过场只测 FPS + 光照 |
| U3 | 复用上周通过的编排 | **二期**：设置页全局场景编排；首版每次重新勾选排序 |
| U4 | 跑到第 3 个场景时失败 | 系统暂停并通知；用户选择重试 / 跳过 / 终止整批（**Q6 已确认**） |
| U5 | 运行中离开页面再回来 | 恢复整批进度：当前第几个场景、该场景处于帧率/指标哪一阶段 |

---

## 4. 功能需求摘要（产品向）

### 4.1 编排配置

- [ ] **默认展示单场景**配置区；点击「多场景」按钮后切换为多场景编排 UI；
- [ ] 多场景模式下可**添加、删除、拖拽/上下移动**调整场景顺序；
- [ ] 场景来源：同一 Unity 项目下 `GET /unity-runner/scenes` 列表（**Q2**）；
- [ ] 每场景条目展示：场景名、`scene_path`；可展开编辑**该场景独立**的：
  - `test_scope`（`MetricScopeSelector`）
  - `collect_interval`
  - `frame_rate_duration_seconds`
  - `metrics_duration_seconds`（**Q7**）
- [ ] 编排级（整批共用）参数：`unity_engine_id`、`batchmode`、`ensure_plugin`；
- [ ] 可选快捷操作：「复制上一场景配置」「从全局默认恢复」（**不做「保存模板」**，**Q5**）；
- [ ] 启动前校验：至少 2 个场景（多场景模式）；每场景至少 1 个叶子指标；场景文件存在且 enabled；所有场景 `project_path` 一致。

### 4.2 执行与监控

- [ ] 一键启动整批；**同一 Editor 内按顺序连续执行**（**Q3**）；
- [ ] 运行中展示：**总进度** + **当前场景序号/总数** + **当前阶段**（与现有 Steps 对齐）；
- [ ] 支持用户**终止整批**；某场景失败后**暂停编排**，弹出/通知用户选择：重试 / 跳过继续 / 终止（**Q6**）；
- [ ] 实时日志/进度带场景前缀：`[场景 2/5 Battle.unity]`；
- [ ] 整批完成后，多场景结果区以 **Tab** 展示各场景数据（**Q4**）。

### 4.3 结果与历史

- [ ] **每场景独立 Session**（**Q4**），`config` 写入 `batch_id`、`scene_index`、`run_mode: multi_scene` 等关联字段；
- [ ] 历史列表增加类型标记：**单场景** / **多场景**；单场景行保持现有样式与跳转；
- [ ] 多场景批次在列表可展开或进入详情，内嵌 **Tab 切换各场景 Session** 的结果（UI 参考单场景 `SessionResultPanel`）；
- [ ] 各场景 `config` 快照保留**该场景当时的 test_scope 与采集时长**，不受后续全局默认变更影响；
- [ ] 首版报表：**按场景独立导出**即可；编排聚合报告为二期可选项。

### 4.4 非目标（首版明确不做）

- 跨**不同 Unity 工程路径**的混合编排（**Q2 已否决**）；
- 每场景单独冷启动 Unity 进程（**Q3 已否决为首版路径**）；
- 编排模板持久化、设置页全局编排（**Q5 二期**）；
- 多 Unity 进程并行跑多个场景；
- 场景间自定义等待脚本（如 A 完成后等待 60s）——二期。

---

## 5. UI 期望（已确认方向 + 待 Codex 细化线框）

### 5.1 入口与模式切换（Q1）

- **默认**：展示现有单场景表单（与当前 `ProjectDetail` 一致）；
- 显眼位置提供 **「多场景测试」** 按钮（或 Segmented：`单场景 | 多场景`）；
- 点击后 **整块配置区切换** 为多场景编排 UI；提供返回单场景的入口；
- 单场景路径**零行为变更**。

### 5.2 多场景编排工作台（建议结构）

```
┌─────────────────────────────────────────────────────────────┐
│  测试配置          [单场景]  [● 多场景]        引擎: Unity …  │
├─────────────────────────────────────────────────────────────┤
│  [+ 添加场景]                                               │
│  ≡ 1. Lobby.unity      [编辑配置] [删除]                    │
│  ≡ 2. Battle.unity     [编辑配置] [删除]                    │
│  ≡ 3. Cutscene.unity   [编辑配置] [删除]                    │
│  （拖拽把手调整顺序）                                        │
│  整批：BatchMode □  自动写 manifest □                        │
│                              [启动多场景测试]                │
└─────────────────────────────────────────────────────────────┘
```

- **无「保存模板」按钮**（Q5）；
- 「编辑配置」展开或 Drawer：**指标 + 采集间隔 + 帧率/指标时长**（Q7）。

### 5.3 逐场景配置编辑（Q7）

- 每场景独立面板，标题：`场景名 + scene_path`；
- 内嵌 `MetricScopeSelector` + 三个 `InputNumber`（间隔、帧率时长、指标时长）；
- 橙色问号提示（设备依赖指标）与单场景一致；
- 新添加场景默认拉取设置页**全局 default_scope** + 默认时长（建议值，见 Q10）；
- 指标摘要 badge：「已选 18/27 项」。

### 5.4 运行中监控

- 顶部：批次 ID、**已完成 / 总场景数**、当前场景名；
- Steps：`(场景 2/5) → 帧率采集 → 指标采集 → 上传`；
- 失败时：**Modal / Notification** 列出失败场景与原因，按钮「重试」「跳过继续」「终止整批」（Q6）；
- 日志分段：`[场景 2/5 Battle.unity]`。

### 5.5 结果与历史（Q4）

**列表层（Sessions / 项目历史）**

| 类型标记 | 展示 |
|----------|------|
| `单场景` | 与现有一致，单行一会话 |
| `多场景` | 批次行或分组头；可显示「3 场景 · 2 完成 1 失败」；子 Session 可折叠列出 |

**详情 / 结果层**

- **单场景**：保持现有单 Tab 结果（`SessionResultPanel` + 跳转分析页）；
- **多场景**：顶部 **Tab 栏**，每个 Tab 对应一个场景的 Session；Tab 内 UI **复用单场景**图表与质量面板；可标明各场景状态（完成/失败/跳过）。

### 5.6 视觉与一致性

- 延续 Ant Design + 现有 `ProjectDetail` / `MetricScopeSelector` 风格；
- 编排列表推荐 Table + 拖拽（`@dnd-kit` 或 Ant Design 生态）或 `Sortable` 列表；
- 移动端非首要目标，但编排列表应支持窄屏纵向堆叠。

---

## 6. 现有技术架构与硬约束

### 6.1 端到端数据流（单场景）

```
ProjectDetail
  → POST /unity-runner/test-tasks/start { scene_resource_id, test_scope, ... }
  → UnityRunnerService.start_test()
  → TestSession + TestTask (各 1 个, scene_id 相同)
  → unity_task_{taskId}_session_{sessionId}.json
  → Unity: OpenScene(Single) → Play Mode → 两阶段采集 → uploadUrl 上传
  → Session.completed → Task.completed
```

### 6.2 关键代码锚点

| 区域 | 路径 | 多场景相关现状 |
|------|------|----------------|
| 测试配置 UI | `frontend/src/pages/Projects/ProjectDetail.tsx` | 单 `scene_resource_id`、单 `testScope` |
| 指标选择 | `frontend/src/components/MetricScopeSelector/` | 单份 scope，无 scene 维度 |
| 启动 API | `backend/app/routers/unity_runner.py` | `UnityStartTestRequest.scene_resource_id` 单值 |
| 编排核心 | `backend/app/services/unity_runner_service.py` | 单场景 JSON、单进程、单 `activeRun` 语义 |
| 指标目录 | `backend/app/services/test_scope_service.py` | 已支持 scope 快照，未绑定 scene |
| 场景发现 | `backend/app/services/system_settings_service.py` | 扫描单 `unity_project_path` 下 `*.unity` |
| Unity 入口 | `unity-xr-collector/Editor/XRBatchTestRunner.cs` | `OpenSceneMode.Single`，无循环 |
| 采集管理 | `unity-xr-collector/Runtime/Core/XRTestManager.cs` | 单会话上传至一个 `platformSessionId` |
| 进度 | `backend/app/routers/progress_ws.py` | key = `task_id`，无 `scene_index` |
| 数据模型 | `backend/app/models/test_session.py` | `scene_id` 单列，无 parent/batch 字段 |
| 数据模型 | `backend/app/models/test_task.py` | 同上，无子任务关系 |

### 6.3 已识别的架构约束

1. **一次启动绑定一个 Unity 工程路径（产品已确认仅同工程）**  
   首版编排内所有场景必须共享同一 `project_path`；启动前须校验，混入不同工程的场景应拒绝并提示。

2. **热启动单槽邮箱**  
   `Library/XRDataCollector/pending-task.json` 为单文件投递；多场景若在同一 Editor 内串行，需定义任务队列协议，避免后写覆盖先写。

3. **Session 与样本归属**  
   `PerformanceSample.test_session_id` 强绑定单 Session。多场景若共用一个 Session，必须在样本层增加场景分段元数据（如 `extra_metrics.scene_resource_id`），否则分析/图表会混在一起。

4. **超时看门狗**  
   `_sync_stale_task` 按 `frame_rate_duration + metrics_duration + 180s` 估算单次运行；多场景需按场景数或编排总时长重算。

5. **run_index / 会话名 `#N`**  
   项目内全局递增。多场景批次下，`#N` 指整批还是每个场景，将直接影响历史列表可读性。

6. **命名误导**  
   `XRBatchTestRunner` 的 “Batch” 指 BatchMode CLI，**不是**多场景批量；扩展时避免语义混淆。

### 6.4 可复用的已有能力

| 能力 | 复用方式 |
|------|----------|
| `test_scope` + `MetricScopeSelector` | 每场景一份 scope 快照，结构已成熟 |
| 全局默认 test_scope（设置页） | 作为编排中各场景的初始模板 |
| `SceneAsset` 去重注册 | 每场景仍可 `_ensure_scene_asset` |
| 进度 WebSocket + Runner 日志 | 扩展 payload 字段而非推倒重来 |
| 单场景分析 / 报表 | 每场景独立 Session 时可直接复用 |
| Sessions 批量导出 ZIP | 可按批次 session 列表批量导出 |

---

## 7. 待 Codex 决策的技术问题（产品已拍板部分见 §2）

> §2 中 Q1–Q7 已确认；以下为实现层仍需方案落笔的细节。

### 7.1 数据模型（在 Q4 约束下）

**已确认**：每场景 **独立 Session**；列表区分单/多场景；多场景详情用 Tab。

**待方案选定：**

- [ ] 是否新增 `TestBatch` 实体（或父 `TestTask`）关联 N 个 Session？推荐：**1 父批次 + N 子 Session**，父级仅负责编排状态，样本仍在各 Session。
- [ ] 父级状态机：`running → awaiting_user_decision`（失败暂停）→ `running | completed | partial_completed | cancelled`。
- [ ] `config` 字段约定：`run_mode`、`batch_id`、`scene_index`、`scene_total`、`batch_task_id`。
- [ ] 会话展示（**Q9 已确认**）：`name` 可仍为 `#N`；UI 主标签用 `scene_display_name`（场景名）；`config` 写入 `batch_id`、`scene_index` 供多场景分组。
- [ ] 数据库：优先 JSON `config` 扩展；若查询批次列表频繁再考虑索引字段。

### 7.2 Unity 执行（Q3 已确认：同 Editor 连续换场景）

**待方案细化：**

- [ ] 任务 JSON 结构：`scenes: [{ unityScenePath, platformSessionId, uploadUrl, testScope, collectInterval, ... }]` 单文件数组 vs 分阶段重写。
- [ ] 场景切换状态机：退 Play Mode → `ClearSamples` → `OpenScene(Single)` → 应用该场景 config → 再进 Play → 巡航 → 采集 → 上传。
- [ ] `quitOnComplete`：仅**整批最后一个场景**完成后为 true（热启动仍为 false）。
- [ ] 失败暂停：插件上报 `batch_status=scene_failed` + 等待后端/用户下发 `retry|skip|abort` 指令（新 API 或队列文件）。
- [ ] 热启动 `pending-task.json`：扩展为队列或单任务内含 `scenes[]`，避免覆盖。
- [ ] 同 Editor 多场景稳定性：对照 `unity-cold-start.md` 制定回归清单（GC、巡航、指标为 0）。

### 7.3 API 形态

- [ ] 建议新增 `POST /unity-runner/test-batches/start`，body：`{ unity_engine_id, batchmode, ensure_plugin, scenes: [{ scene_resource_id, test_scope, collect_interval, frame_rate_duration_seconds, metrics_duration_seconds }] }`。
- [ ] 失败决策：`POST /unity-runner/test-batches/{batch_id}/decision` `{ action: retry | skip | abort }`。
- [ ] 进度 payload 扩展：`batch_id`、`scene_index`、`scene_total`、`scene_resource_id`、`scene_session_id`、`batch_status`。
- [ ] **不做**编排模板 CRUD（Q5）。

### 7.4 配置粒度（Q7 已确认）

| 配置项 | 粒度 |
|--------|------|
| `test_scope` | **每场景独立** |
| `collect_interval` | **每场景独立** |
| `frame_rate_duration_seconds` | **每场景独立** |
| `metrics_duration_seconds` | **每场景独立** |
| `unity_engine_id` | 编排级 |
| `batchmode` / `ensure_plugin` | 编排级 |

新加场景默认值：建议拉取设置页全局 default_scope + 单场景默认时长（Q10）。

### 7.5 失败与恢复（Q6 已确认）

- [ ] 失败时编排进入 `awaiting_user_decision`，**不自动** skip 或 abort。
- [ ] 前端 Modal 三选项：重试当前 / 跳过继续 / 终止整批。
- [ ] 跳过后标记该 Session `failed` 或 `skipped`（需新状态或 config 标记），继续下一场景。
- [ ] 刷新页面：根据 `batch_id` + running 父任务恢复监控（扩展 `activeBatch`）。
- [ ] 同项目禁止并行两个编排（建议首版强制）。

### 7.6 前端

- [ ] `activeRun` → `activeBatch`：`{ batchId, taskId, scenes: [{ sessionId, sceneName, status }], currentSceneIndex }`。
- [ ] WebSocket：订阅父 `task_id` 或 `batch_id` 统一通道。
- [ ] 多场景结果 Tab：每 Tab `sessionId` 驱动现有 `SessionResultPanel`。
- [ ] Sessions 列表：`run_mode` 列 + 多场景分组/筛选。

### 7.7 分析、报表

- [ ] 首版：各场景独立分析页 / 独立报表（复用现有）。
- [ ] 二期：多场景 FPS 对比、编排聚合 PDF。
- [ ] `batch-generate`：可选支持按 `batch_id` 导出 ZIP（首版 P2）。

### 7.8 测试

- [ ] 后端：批次启动校验、同工程检查、失败决策流、scope/时长 per-scene 写入快照。
- [ ] Unity：至少 2 场景串行集成测试用例（或手动回归脚本）。

---

## 8. 开放问题（可选，不阻塞方案）

| ID | 问题 | 说明 |
|----|------|------|
| **Q8** | 场景级备注字段 | 未确认是否需要 |
| **Q10** | 新加场景默认指标来源 | 建议全局 default_scope，方案中写死即可 |

---

## 9. 与现有文档/功能的关系

| 已有项 | 关系 |
|--------|------|
| `docs/problems/selectable-test-metrics-plan.md` | 指标可选已实施；多场景 = 每场景一份 scope |
| `docs/solve/selectable-test-metrics-implementation-plan.md` | `test_scope` 快照机制可复用 |
| `docs/problems/unity-cold-start.md` | 同进程多场景需评估冷启动/GC/采集差异 |
| 单场景 `ProjectDetail` | 保留，新增编排模式并列 |
| `MetricScopeSelector` | 每场景实例化一份，注意性能（场景数上限） |
| 报表 HTML/PDF 导出 | 每场景 Session 已有；批次聚合为增量需求 |

---

## 10. 建议方案交付物（供 Codex 对照）

1. **领域模型**：Batch + N Session 关系图（§2 Q4）  
2. **API 设计**：`test-batches/start`、失败 `decision`、进度字段扩展  
3. **Unity 协议**：同 Editor `scenes[]` 循环、失败暂停与 resume 指令  
4. **前端**：默认单场景 + 按钮切换多场景；编排列表；per-scene 配置 Drawer；失败 Modal；结果 Tab  
5. **历史列表**：`单场景` / `多场景` 标记与分组展示  
6. **监控与日志**：`activeBatch`、场景分段日志  
7. **数据库 / config** 约定  
8. **二期占位**：设置页全局编排（Q5）、聚合报告  
9. **测试计划**与**验收清单**  

---

## 11. 验收标准（含产品决策）

- [ ] 默认进入**单场景** UI；点击按钮可切换多场景编排 UI，并可切回  
- [ ] 多场景模式可添加、删除、排序 ≥2 个**同 Unity 工程**场景  
- [ ] 每场景可独立配置 `test_scope`、采集间隔、帧率/指标时长，并写入各自 Session 快照  
- [ ] 同 Editor 内按顺序自动连续执行，无需逐场景手动启动  
- [ ] 运行中展示「第几个场景 / 共几个 / 当前阶段」  
- [ ] 某场景失败时通知用户，并提供重试 / 跳过 / 终止选项（**不自动**继续或停止）  
- [ ] 每场景独立 Session；历史列表有**单场景 / 多场景**标记  
- [ ] 列表与详情**主标签显示场景名**（`测试场景` Tag），`#N` 为次要会话标识（**Q9**）  
- [ ] 多场景结果区以 **Tab** 切换各场景，Tab 标题为场景名，Tab 内 UI 与单场景一致  
- [ ] **无**编排模板保存；单场景路径无回归  
- [ ] 关键路径有后端测试覆盖  

---

## 12. 关键文件索引

| 区域 | 路径 |
|------|------|
| 测试配置 / 监控 | `frontend/src/pages/Projects/ProjectDetail.tsx` |
| 指标选择 | `frontend/src/components/MetricScopeSelector/` |
| scope 工具 | `frontend/src/lib/testScope.ts` |
| 启动 API 类型 | `frontend/src/api/unityRunner.ts` |
| Unity Runner 路由 | `backend/app/routers/unity_runner.py` |
| 启动与任务 | `backend/app/services/unity_runner_service.py` |
| 指标 scope | `backend/app/services/test_scope_service.py` |
| 场景发现 | `backend/app/services/system_settings_service.py` |
| 进度 WS | `backend/app/routers/progress_ws.py` |
| 样本上传 | `backend/app/routers/data_collection.py` |
| Session 模型 | `backend/app/models/test_session.py` |
| Task 模型 | `backend/app/models/test_task.py` |
| Unity 场景打开 | `unity-xr-collector/Editor/XRBatchTestRunner.cs` |
| Unity 采集 | `unity-xr-collector/Runtime/Core/XRTestManager.cs` |
| 性能分析 | `backend/app/services/performance_analysis_service.py` |
| 详细报表 | `backend/app/services/detailed_report_builder.py` |
| 历史会话列表 | `frontend/src/pages/Sessions/index.tsx` |

---

## 13. 附录：单场景任务 JSON 参考（扩展基线）

当前 `_write_task_config()` 每个任务仅包含一组：

- `unityScenePath`（单值）
- `platformSessionId` / `uploadUrl`（单会话）
- `requestedMetricIds` / `qualityMetricChecks`（单份 scope 派生）

多场景方案需明确上述字段如何扩展为**列表**或**多文件队列**。完整字段表见 `docs/17-网页启动Unity本地测试.md` 与 `unity_runner_service._write_task_config()`。

---

**请 Codex 基于本文档 §2（已确认决策）、§4–§5（需求与 UI）、§7（技术待决）输出 `docs/solve/multi-scene-orchestration-implementation-plan.md`。**
