# 测试指标可配置化计划（Problem / Plan Document）

> 文档用途：描述「测试指标可选、全局默认、跳过展示」的产品计划与现有代码上下文，供 Codex / 开发协作实施时参考。  
> 最后更新：2026-06-11  
> 状态：**待实施**

---

## 1. 背景与目标

当前 XR 渲染测试工具已能采集多类性能与渲染质量指标，但测试范围基本是**固定或部分固定**的：

- 项目详情页仅有 4 项「渲染质量测试项」可勾选；
- 基础性能指标（FPS、CPU、内存等）默认全开，用户无法在测试前按需裁剪；
- 设置页仅支持 Unity 路径与默认场景，不支持配置默认测试指标；
- 未测试的指标在监控页、结果页、分析页缺少统一的「跳过」表达，容易让用户误以为采集失败或值为 0。

**目标：**

1. 提供测试软件所要测试的**全部指标**清单；
2. 测试开始前允许用户选择哪些指标需要测试，**仅勾选项参与采集、分析与展示**；
3. 设置页新增 Tab「测试指标」，配置**全局默认测试指标**；
4. 测试进行页与结果显示页：未勾选指标显示**跳过**，页面顶部展示**本次测试范围**；
5. 系统行为可靠，界面美观，与现有产品风格一致。

本文档只描述计划与有用信息，**不包含具体实施步骤**；实施细节由 Codex 在此基础上展开。

---

## 2. 计划一：全部可测指标清单

### 2.1 目标

建立一份**完整、结构化、可勾选**的测试指标目录，作为以下能力的统一数据源：

- 测试前指标选择；
- 设置页全局默认配置；
- 监控/结果/分析页的跳过展示；
- Unity 采集裁剪与后端评分裁剪。

### 2.2 指标分层（与现有代码对齐）

#### A. 基础性能指标（`metric_checks`）

对应 Unity `XRTestConfig` 与后端 `unity_runner` 启动参数。

| ID（建议） | 中文名 | 现有字段 / 配置 |
|------------|--------|-----------------|
| `frame_rate` | 帧率 FPS | `collectFrameRate` |
| `frame_time` | 帧时间 | `collectFrameTime` |
| `cpu` | CPU 使用率 | `collectCpuUsage` |
| `gpu` | GPU 使用率 / 渲染统计 | `collectGpuUsage`（含 Draw Call、三角面、顶点） |
| `memory` | 内存 | `collectMemory`（总内存、托管堆、显存、系统预留） |
| `device_info` | 设备信息 | `collectDeviceInfo`（硬件、XR、分辨率、渲染管线等） |

#### B. 渲染质量大类（`quality_checks`）

测试页已有 4 项 Checkbox，需纳入统一目录。

| ID | 中文名 |
|----|--------|
| `lighting` | 光照与阴影 |
| `materials` | 材质与纹理 |
| `post_processing` | 后处理 |
| `physics` | 物理仿真 |

#### C. 渲染质量细分指标（`quality_metric_checks`）

后端 `_quality_metric_payload` 已定义 key，前端尚未完整暴露 UI。

**光照与阴影**

| key | 中文名（建议） |
|-----|----------------|
| `lighting.active_lights` | 活动光源数量 |
| `lighting.realtime_lights` | 实时光源数量 |
| `lighting.shadow_casters` | 阴影投射体数量 |
| `lighting.reflection_probes` | 反射探针数量 |
| `lighting.exposure_artifacts` | 曝光异常标记 |

**材质与纹理**

| key | 中文名（建议） |
|-----|----------------|
| `materials.material_slots` | 材质槽数量 |
| `materials.unique_materials` | 去重材质数量 |
| `materials.transparent_materials` | 透明材质数量 |
| `materials.draw_calls` | Draw Call |
| `materials.texture_memory` | 纹理内存 |

**后处理**

| key | 中文名（建议） |
|-----|----------------|
| `post_processing.volumes` | 后处理 Volume 数量 |
| `post_processing.render_textures` | RenderTexture 数量 |
| `post_processing.render_texture_memory` | RenderTexture 内存 |
| `post_processing.gpu_frame_budget` | GPU 帧预算压力 |
| `post_processing.warnings` | 后处理警告标记 |

**物理仿真**

| key | 中文名（建议） |
|-----|----------------|
| `physics.rigidbodies` | 刚体数量 |
| `physics.colliders` | 碰撞体数量 |
| `physics.penetration` | 穿模/碰撞异常 |
| `physics.pose_latency` | 姿态延迟 |
| `physics.prediction_error` | 预测误差 |
| `physics.long_frames` | 物理导致长帧 |

#### D. 后端分析 / 评分衍生项（结果页展示，不一定由 Unity 实时采集）

| 分组 | 指标示例 |
|------|----------|
| 稳定性 | 平均 FPS、P95/P99 帧时、长帧次数、掉帧率、风险等级 |
| 资源 | SetPass、峰值纹理/网格/RT 内存、GC 分配 |
| 热管理 | 电池温度、超温次数（真机预留） |
| 参考帧 | SSIM、PSNR、Delta E（需额外输入，未选或无数据应显示跳过） |
| 阈值 | 可配置规则的违规告警 |

### 2.3 产品规则（需 Codex 在设计中落实）

- 每个可选项需有：**稳定 ID、中文展示名、所属分组、是否默认开启、父级依赖**。
- **父子关系**：未勾选大类时，其下细分项视为跳过；大类勾选后可再细选子项（若支持二级勾选）。
- 区分 **「采集项」**（Unity 是否采集/上报）与 **「展示/评分项」**（后端是否分析与扣分），避免用户勾选后却无数据。
- **全不勾选**时应禁止启动测试，并给出明确提示。

### 2.4 相关代码位置

| 区域 | 路径 |
|------|------|
| 前端类型 | `frontend/src/api/unityRunner.ts` |
| 启动请求 | `UnityTestStartRequest.metric_checks` / `quality_checks` / `quality_metric_checks` |
| 任务配置组装 | `backend/app/services/unity_runner_service.py` → `_build_task_config`、`_quality_metric_payload` |
| Unity 配置 | `unity-xr-collector/Runtime/Core/XRTestConfig.cs` |
| Unity 质量采集 | `unity-xr-collector/Runtime/Collectors/RenderQualityCollector.cs`（未启用项赋 `-1`） |
| 会话持久化 | `TestSession.config` |
| 质量评分 | `backend/app/services/render_quality_service.py` → `_enabled_quality_checks`、`_untested_category` |
| 中文标签 | `frontend/src/lib/renderQualityLabels.ts` |

---

## 3. 计划二：设置页新增 Tab「测试指标」

### 3.1 目标

在 **系统设置**（`frontend/src/pages/Settings/index.tsx`）中：

- 将现有内容归入 Tab：**「Unity 本地测试路径」**（保持现有 Unity 可执行文件、项目目录、插件路径、默认场景）；
- 新增 Tab：**「测试指标」**，用于配置**全局默认测试指标**。

### 3.2 行为预期

- 管理员在「测试指标」Tab 勾选默认要测的指标（结构与计划一一致）。
- 保存后持久化到系统设置（参考现有 `unity_scene_path` 的存取方式）。
- 用户进入项目详情测试配置时，**默认勾选**来自全局设置；仍可在单次测试前覆盖。
- 若全局未配置，回退到系统内置默认（建议：4 项质量全选 + 6 项基础性能全开，与当前行为一致）。

### 3.3 相关代码位置

| 区域 | 路径 |
|------|------|
| 设置页 | `frontend/src/pages/Settings/index.tsx` |
| 设置 API | `backend/app/routers/system_settings.py` |
| 设置服务 | `backend/app/services/system_settings_service.py` |
| 存储文件 | `runtime/system_settings.json`（`SYSTEM_SETTINGS_PATH`） |
| 前端 API | `frontend/src/api/systemSettings.ts` |
| 先例 | 默认场景 `unity_scene_path` + `is_default` 下发至测试页 |

### 3.4 界面一致性

- 使用 Ant Design `Tabs`、`Card`、`Checkbox.Group` 或分组 `Tree`；
- Tab 样式与 `ProjectDetail` 的「Unity 本地测试 / 历史测试记录」保持同一视觉语言。

---

## 4. 计划三：跳过展示 + 顶部测试范围说明

### 4.1 目标

用户未勾选的指标，在**测试进行中**和**结果显示**时不应空白或显示 0 造成误解，而应明确显示 **「跳过 / 未测试」**；页面顶部展示**本次实际测试范围**。

### 4.2 涉及页面

| 页面 | 路径 |
|------|------|
| 项目详情 — Unity 测试 / 监控面板 | `frontend/src/pages/Projects/ProjectDetail.tsx` |
| 测试结束内嵌结果 | `frontend/src/components/SessionResultPanel/` |
| 性能分析页 | `frontend/src/pages/Analysis/index.tsx` |
| 渲染质量面板 | `frontend/src/components/RenderQualityPanel/` |
| 设备信息面板 | `frontend/src/components/SessionDeviceInfoPanel/` |

### 4.3 行为预期

**顶部横幅（Alert）示例：**

> 本次测试范围：FPS、帧时间、CPU、光照与阴影、材质与纹理  
> 已跳过：GPU、后处理、物理仿真、设备信息

**监控面板：**

- 跳过的指标行显示灰色 Tag「跳过」，不展示假数据或长期为 0 的误导值。

**结果 / 分析页：**

- 跳过的质量大类显示「未测试」卡片（`render_quality_service._untested_category` 已有类似逻辑）；
- 跳过的性能图表显示占位说明，而非空图或全 0 曲线。

**历史会话：**

- 从 `session.config` / `task.config` 读取**当时**的勾选快照，不能仅依赖当前全局默认设置。

**报告导出：**

- 标注哪些项未纳入本次测试，避免验收误解。

### 4.4 数据流要求（供 Codex 设计）

```
设置页全局默认
    ↓
项目详情测试配置（可覆盖）
    ↓
启动测试 → 写入 TestTask.config + TestSession.config（完整勾选快照）
    ↓
Unity 按勾选裁剪采集
    ↓
后端按勾选裁剪评分 / 分析
    ↓
前端监控 / 结果 / 分析页按快照展示范围横幅 + 跳过态
```

### 4.5 相关代码位置

| 能力 | 路径 |
|------|------|
| 中文标签 | `frontend/src/lib/renderQualityLabels.ts` |
| 状态色 | `getStatusColor`（通过 / 需关注 / 未测试） |
| 质量证据字段 | `RenderQualityPanel` → `has_runtime_quality_metrics`、`enabled_quality_checks` |
| 会话 config 读取 | `ProjectDetail.tsx`、`frontend/src/lib/sessionConfig.ts` |

---

## 5. 计划四：可靠性、美观与一致性

### 5.1 可靠性

- 勾选配置在冷启动 / 热启动、停止、Unity 域重载后不丢失。
- 前后端、Unity 使用**同一套指标 ID**；统一 camelCase / snake_case 转换层。
- 历史会话回放时，展示以**会话快照**为准，不受后续全局默认变更影响。
- 可选：进度 WebSocket payload 携带当前阶段与已启用指标摘要。

### 5.2 美观与一致性

- 指标选择 UI：分组折叠（基础性能 / 渲染质量大类 / 细分指标）。
- 跳过态统一组件，例如 `MetricSkippedPlaceholder`，文案统一为「未纳入本次测试」。
- 监控态 Tag 与「等待 Unity」「采集中」「跳过」色系协调。
- 全站指标中文名来自**单一目录源**（扩展 `renderQualityLabels.ts` 或新增 `metricsCatalog.ts`）。
- **跳过**与**采集值为 0**、**采集失败**要在视觉上可区分。

---

## 6. 建议实施优先级

| 优先级 | 内容 |
|--------|------|
| **P0** | 指标目录定义 + 全局默认（设置 Tab）+ 测试前勾选 + 写入 session config |
| **P0** | 结果 / 分析页跳过展示 + 顶部测试范围横幅 |
| **P1** | 监控面板实时区跳过态 + 二级细分指标 UI |
| **P2** | 报告导出标注跳过项 + 参考帧类指标纳入同一勾选体系 |

---

## 7. 建议 Codex 交付物清单

1. **指标目录定义**（前后端共享）：ID、label、group、default、parentId、collect / analyze 标志  
2. **系统设置 schema 扩展**：如 `default_metric_checks`、`default_quality_checks`、`default_quality_metric_checks`  
3. **设置页 UI**：双 Tab + 保存 / 重置默认  
4. **项目详情测试配置 UI**：继承全局默认 + 单次覆盖 + 全不选校验  
5. **会话 config 快照**：启动测试时完整持久化  
6. **Unity / 后端**：按勾选裁剪采集与评分（补齐尚未打通的细分项）  
7. **监控页 + 结果页 + 分析页**：顶部范围横幅 + 跳过占位 + 未测试类别  
8. **测试**：设置读写、启动 payload、跳过展示、历史会话回放  

---

## 8. 关键文件索引

| 区域 | 路径 |
|------|------|
| 设置页 | `frontend/src/pages/Settings/index.tsx` |
| 测试配置 / 监控 | `frontend/src/pages/Projects/ProjectDetail.tsx` |
| 结果面板 | `frontend/src/components/SessionResultPanel/` |
| 质量面板 | `frontend/src/components/RenderQualityPanel/` |
| 指标文案 | `frontend/src/lib/renderQualityLabels.ts` |
| 启动 API | `frontend/src/api/unityRunner.ts`、`backend/app/routers/unity_runner.py` |
| 任务配置 | `backend/app/services/unity_runner_service.py` |
| 系统设置 | `backend/app/services/system_settings_service.py` |
| 质量评分 | `backend/app/services/render_quality_service.py` |
| 性能分析 | `backend/app/services/performance_analysis_service.py` |
| Unity 配置 | `unity-xr-collector/Runtime/Core/XRTestConfig.cs` |
| Unity 上传 | `unity-xr-collector/Runtime/Network/TestDataUploader.cs` |

---

## 9. 与现有能力的关系

| 已有能力 | 本计划中的位置 |
|----------|----------------|
| 测试页 4 项渲染质量 Checkbox | 并入统一指标目录，并支持全局默认 |
| `quality_metric_checks` 后端 payload | 暴露为设置页 / 测试页可选细分项 |
| `RenderQualityService._untested_category` | 扩展为所有跳过项的统一后端语义 |
| 默认 Unity 场景（`unity_scene_path`） | 与「测试指标」Tab 并列，同属系统设置 |
| 分析页从 `session.config` 读配置 | 扩展为读取完整指标勾选快照 |

---

## 10. 验收标准（摘要）

- [ ] 设置页可配置全局默认指标并持久化  
- [ ] 测试开始前可选择指标，未选项不参与采集  
- [ ] 启动后 session / task config 含完整勾选快照  
- [ ] 监控页、结果页、分析页顶部显示本次测试范围  
- [ ] 未勾选指标统一显示「跳过 / 未测试」，不与 0 值或失败混淆  
- [ ] 历史会话打开后仍显示当时的测试范围，不受全局默认变更影响  
- [ ] 全不勾选时无法启动测试  
- [ ] UI 风格与现有 Settings、ProjectDetail、Analysis 页一致  
