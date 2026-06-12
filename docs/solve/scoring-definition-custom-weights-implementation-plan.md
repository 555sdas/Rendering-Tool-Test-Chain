# 评分定义自定义权重实施方案

> 目标：在系统设置页新增“评分定义”Tab，允许管理员自定义渲染质量四个评分分类的权重，并保证现有测试、历史结果和评分逻辑保持稳定。  
> 实施对象：Cursor Agent  
> 文档日期：2026-06-12

## 1. 实施结论

本次建议只开放“分类权重”配置，不开放指标阈值、单条扣分值和等级分界线。

可配置的四个分类为：

| 分类 ID | 前端名称 | 当前默认权重 |
| --- | --- | ---: |
| `lighting` | 光照与阴影 | 25% |
| `material` | 材质与纹理 | 25% |
| `post_processing` | 后处理与画面一致性 | 25% |
| `physics` | 物理仿真与虚实融合 | 25% |

核心原则：

1. 四项权重之和必须等于 100%。
2. 配置修改只影响修改后创建的新测试。
3. 每次创建测试时，将评分定义快照写入测试会话配置。
4. 分析历史测试时使用其快照，不读取当前系统设置。
5. 老会话没有快照时，始终使用内置默认权重 `25/25/25/25`。
6. 保持当前扣分规则、指标状态、完整度和置信等级逻辑不变。
7. `ThresholdRule` 继续用于性能指标告警，不与评分定义合并。

这种实现可以满足用户自定义比重的需求，同时避免修改设置后历史报告分数发生漂移。

## 2. 当前实现基线

### 2.1 前端设置页

当前设置页位于：

- `frontend/src/pages/Settings/index.tsx`

已有 Tab：

- `Unity 本地测试路径`
- `测试指标`

建议新增第三个 Tab：

- key：`scoring-definition`
- label：`评分定义`

评分定义应拥有独立的加载、保存、重置和错误状态，不能与 Unity 路径或测试指标设置共用保存状态。

### 2.2 后端系统设置

当前系统设置接口与存储主要位于：

- `backend/app/routers/system_settings.py`
- `backend/app/services/system_settings_service.py`
- `backend/runtime/system_settings.json`

现有设置按独立字段保存，例如 `unity`、`test_metrics`。本次应新增独立的 `scoring_definition` 字段，避免覆盖其他设置。

### 2.3 当前评分逻辑

当前渲染质量评分位于：

- `backend/app/services/render_quality_service.py`

当前四个分类权重由硬编码的 `CATEGORY_WEIGHTS` 提供，默认均为 25。总分只统计参与测试的分类，并对这些分类的权重重新归一化。

本次只替换分类权重来源，不调整以下逻辑：

- 各指标的采集与五态展示
- 各评分项的扣分条件和扣分值
- 分类得分计算
- 数据完整度
- 置信等级
- 分类状态和总分等级阈值

## 3. 功能范围

### 3.1 本期必须实现

- 设置页新增“评分定义”Tab。
- 展示四个分类及其权重。
- 支持编辑、保存、恢复系统默认值。
- 权重总和实时校验，必须为 100% 才能保存。
- 新测试创建时保存评分定义快照。
- 分析结果使用会话快照计算。
- 结果页显示本次测试实际使用的分类权重。
- 老配置、老会话和现有 API 保持兼容。

### 3.2 本期明确不实现

- 用户自定义每条规则的扣分值。
- 用户自定义指标阈值。
- 用户自定义 A/B/C/D 等级分界线。
- 按项目、设备、场景配置不同权重。
- 多套具名评分模板。
- 使用新权重静默重算历史测试。

上述能力可以作为后续版本扩展，但不应混入本次改动。

## 4. 数据模型设计

### 4.1 系统设置结构

在 `backend/runtime/system_settings.json` 增加：

```json
{
  "scoring_definition": {
    "schema_version": 1,
    "category_weights": {
      "lighting": 25,
      "material": 25,
      "post_processing": 25,
      "physics": 25
    }
  }
}
```

不要把分类中文名称写入用户设置。分类名称和说明应由代码内的分类目录统一维护，避免配置文件内容过时。

为后续扩展预留 `schema_version`，但本期不要提前写入未实现的 `rule_overrides`、`grade_thresholds` 等字段。

### 4.2 后端校验规则

保存评分定义时必须严格校验：

- 必须包含四个已知分类。
- 不允许未知分类 ID。
- 每项必须为有限数字，不能为 `NaN`、`Infinity` 或字符串。
- 每项范围为 `0 <= weight <= 100`。
- 四项总和必须等于 100，浮点误差容差建议为 `0.01`。
- 至少一项权重大于 0。

建议保存接口要求提交完整的四项权重，不接受部分更新。这样可以避免客户端和服务端对缺失字段采用不同默认值。

### 4.3 权重为 0 的语义

权重为 0 表示：

- 该分类仍然执行评分并展示结果。
- 该分类不计入总分。
- 它不等同于用户没有选择该分类进行测试。

如果某次测试中，所有参与测试分类的有效权重均为 0，则总分应返回 `null`，并返回明确原因，不能除以 0 或返回误导性的 0 分。

## 5. 后端实施方案

### 5.1 新增评分定义服务

建议新增：

- `backend/app/services/scoring_definition_service.py`

该服务作为评分定义的唯一事实来源，负责：

- 内置默认权重。
- 分类 ID、名称和说明目录。
- 读取并标准化系统设置。
- 严格校验用户提交的配置。
- 保存和重置配置。
- 从测试会话解析评分定义快照。
- 对旧会话提供稳定默认值。

建议提供类似以下方法：

```python
get_builtin_definition()
get_catalog()
get_global_definition()
validate_definition(definition)
save_global_definition(definition)
reset_global_definition()
resolve_session_definition(session_config)
```

`render_quality_service.py` 不应直接读取 JSON 文件，也不应在每个分类评分函数中查询系统设置。

### 5.2 新增独立系统设置 API

在 `backend/app/routers/system_settings.py` 新增：

```text
GET  /api/v1/system-settings/scoring-definition
PUT  /api/v1/system-settings/scoring-definition
POST /api/v1/system-settings/scoring-definition/reset
```

所有接口沿用现有系统设置权限：

- `Permission.SYSTEM_CONFIG`

建议 GET 响应同时提供设置、目录和总计，减少前端额外请求：

```json
{
  "definition": {
    "schema_version": 1,
    "category_weights": {
      "lighting": 25,
      "material": 25,
      "post_processing": 25,
      "physics": 25
    }
  },
  "catalog": {
    "categories": [
      {
        "id": "lighting",
        "label": "光照与阴影",
        "description": "实时光源、阴影与反射相关质量"
      }
    ]
  },
  "summary": {
    "total_weight": 100,
    "is_default": true
  }
}
```

PUT 保存成功后返回标准化后的完整配置。非法配置返回 `422`，并给出可供前端展示的具体错误原因。

保存和重置操作必须写审计日志，审计内容至少包括修改前后的四项权重。

### 5.3 将评分定义快照写入新测试

测试创建链路中应在后端生成测试配置时读取一次当前全局评分定义，并写入：

```json
{
  "scoring_definition": {
    "schema_version": 1,
    "category_weights": {
      "lighting": 40,
      "material": 30,
      "post_processing": 20,
      "physics": 10
    }
  }
}
```

需要检查并覆盖测试任务和测试会话的创建路径，确保最终的 `TestTask.config` 与 `TestSession.config` 都能保留该快照。优先在统一构建测试配置的方法中注入，避免多个入口行为不一致。

Unity 插件无需理解或使用评分定义。评分由后端完成，快照只需要保存在后端测试配置中。

### 5.4 改造评分服务

在 `render_quality_service.py` 中：

1. 移除业务计算对硬编码 `CATEGORY_WEIGHTS` 的直接依赖。
2. 分析会话时，通过 `resolve_session_definition(session.config)` 获取权重。
3. 将解析后的权重传入分类结果和总分计算。
4. 保留现有“只对参与测试分类重新归一化”的行为。
5. 保留现有扣分逻辑和所有阈值。

示例：

配置权重为 `40/30/20/10`，本次只测试前三类，则总分分母为 `90`，不是 `100`。

建议分析响应增加：

```json
{
  "scoring_definition": {
    "schema_version": 1,
    "category_weights": {
      "lighting": 40,
      "material": 30,
      "post_processing": 20,
      "physics": 10
    }
  },
  "scoring_definition_source": "session_snapshot",
  "score_formula": {
    "effective_total_weight": 90,
    "included_categories": ["lighting", "material", "post_processing"]
  }
}
```

分类结果中保留现有 `weight` 字段以兼容前端，并明确它表示该分类的配置权重。如有展示需要，可新增 `included_in_overall_score`，不要改变旧字段语义。

### 5.5 历史数据兼容

解析评分定义时必须按以下顺序：

1. 会话配置中存在合法 `scoring_definition`：使用会话快照。
2. 会话配置没有快照：使用内置默认 `25/25/25/25`。
3. 会话快照存在但损坏：回退内置默认，并在响应中标记回退原因、记录告警日志。

严禁让没有快照的老测试读取当前全局评分设置，否则用户修改设置后，旧报告会出现分数变化。

如果未来需要使用新配置重算历史测试，应提供显式的“重新计算”操作，并标记为派生结果，不能覆盖原始结果。

## 6. 前端实施方案

### 6.1 API 与类型

在 `frontend/src/api/systemSettings.ts` 增加评分定义相关类型和 API：

```ts
getScoringDefinition()
updateScoringDefinition(payload)
resetScoringDefinition()
```

建议定义明确类型：

```ts
type ScoringCategoryId =
  | 'lighting'
  | 'material'
  | 'post_processing'
  | 'physics'

interface ScoringDefinition {
  schema_version: number
  category_weights: Record<ScoringCategoryId, number>
}
```

不要使用宽泛的 `Record<string, number>` 作为页面编辑状态，否则分类拼写错误无法在编译期发现。

### 6.2 新增评分定义编辑组件

建议新增：

- `frontend/src/components/ScoringDefinitionEditor/index.tsx`

页面内容建议包括：

- 四个分类卡片或表格行。
- 分类名称和简短说明。
- `InputNumber` 精确输入权重。
- `Slider` 快速调整权重。
- 实时显示权重总和。
- 实时显示总分公式预览。
- “保存评分定义”按钮。
- “恢复系统默认”按钮。
- 可选的“平均分配”按钮。

实时公式示例：

```text
总分 = 光照与阴影 × 40% + 材质与纹理 × 30%
     + 后处理与画面一致性 × 20% + 物理仿真与虚实融合 × 10%
```

交互约束：

- 总和为 100% 时显示通过状态。
- 总和不为 100% 时显示差额，并禁用保存。
- 输入为空、非数字或越界时立即提示。
- 重置操作需要二次确认。
- 保存后使用后端返回的标准化配置刷新页面。

页面顶部应明确提示：

- 修改仅影响之后创建的新测试。
- 历史测试继续使用创建时的评分定义。
- 权重为 0 的分类仍会展示，但不计入总分。
- 当前评分属于风险评估模型，不代表认证结论。

### 6.3 接入设置页 Tab

在 `frontend/src/pages/Settings/index.tsx` 增加：

```text
评分定义
```

评分定义使用独立状态，例如：

```ts
scoringDefinition
scoringLoading
scoringSaving
scoringError
```

建议将现有设置加载逻辑拆为独立请求，或使用 `Promise.allSettled`。评分定义接口失败时，不应导致 Unity 路径和测试指标两个已有 Tab 无法使用。

### 6.4 结果页展示

结果页应显示本次测试实际采用的权重，而不是当前系统设置中的权重。

建议在渲染质量分析区域增加“评分定义”摘要：

- 各分类配置权重。
- 本次实际参与总分计算的分类。
- 有分类未参与时，提示总分进行了权重归一化。
- 快照缺失并回退默认值时，显示“旧版测试，使用系统内置默认权重”。

现有分类卡片中的“权重 25%”应继续使用分析接口返回的 `weight`，不要额外请求当前系统评分设置。

## 7. 建议实施顺序

### 阶段一：建立后端配置能力

1. 新增 `scoring_definition_service.py`。
2. 增加默认值、目录、校验、读取、保存、重置能力。
3. 在 `system_settings.py` 增加独立 API。
4. 增加权限和审计日志测试。

完成标准：管理员可以通过 API 保存和恢复四项权重，现有系统设置不受影响。

### 阶段二：接入测试会话快照

1. 找到统一测试配置构建入口。
2. 创建新测试时注入评分定义快照。
3. 确认任务与最终会话均保存快照。
4. 为老会话实现固定默认值回退。

完成标准：修改全局权重后，旧会话配置和分析结果不变，新会话包含新快照。

### 阶段三：改造评分计算

1. 使用会话快照替代固定分类权重。
2. 保持原有参与分类归一化行为。
3. 处理零权重和全部有效权重为零的情况。
4. 在分析响应中返回评分定义与公式摘要。

完成标准：默认配置下现有评分结果完全不变，自定义权重下总分计算正确。

### 阶段四：实现设置页与结果页展示

1. 增加前端 API 和类型。
2. 新增评分定义编辑器。
3. 接入设置页第三个 Tab。
4. 在结果页展示会话实际评分权重。
5. 隔离各设置 Tab 的加载失败。

完成标准：用户可完成加载、编辑、校验、保存、重置，并能在新测试结果中看到实际使用的权重。

## 8. 测试方案

### 8.1 后端单元测试

新增评分定义服务和 API 测试，至少覆盖：

- 无配置时返回 `25/25/25/25`。
- 合法配置保存后可重新读取。
- 重置后恢复默认值。
- 总和不等于 100 时拒绝保存。
- 缺失分类时拒绝保存。
- 包含未知分类时拒绝保存。
- 负数、超过 100、非数字、非有限数字时拒绝保存。
- 保存和重置产生审计日志。
- 修改评分定义不会覆盖 `unity` 和 `test_metrics` 设置。

### 8.2 评分与快照测试

至少覆盖：

- 新测试包含当前评分定义快照。
- 修改全局配置后，已有测试分析结果不变。
- 老测试没有快照时使用固定默认权重。
- 默认权重下的评分结果与改造前完全一致。
- 自定义权重下总分计算正确。
- 未参与测试的分类不进入分母。
- 权重为 0 的分类仍有分类结果，但不进入总分。
- 所有参与分类有效权重为 0 时，总分为 `null` 且包含原因。
- 损坏快照回退默认值并返回回退标记。

### 8.3 前端测试

至少覆盖：

- 第三个 Tab 正常显示。
- 初次加载展示后端权重。
- 总和为 100 时允许保存。
- 总和不为 100 时禁用保存并提示差额。
- 保存后使用后端响应刷新。
- 重置后恢复默认值。
- 评分定义加载失败不影响另外两个设置 Tab。
- 结果页使用分析响应中的快照权重。

### 8.4 回归命令

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -q

cd ../frontend
npm run check
npm run build
```

## 9. 验收标准

- 设置页出现“评分定义”Tab。
- 管理员可以配置四个分类权重并保存。
- 权重总和不为 100% 时无法保存。
- 保存、重置操作具备权限校验和审计记录。
- 默认配置下现有测试得分不发生变化。
- 新配置只影响之后创建的新测试。
- 历史测试始终使用会话快照或固定内置默认值。
- 结果页显示本次测试实际采用的评分权重。
- 零权重、分类未测试、旧会话回退均有明确说明。
- 现有 Unity 路径、测试指标、采集、上传、分析流程保持正常。
- 后端测试、前端检查和构建全部通过。

## 10. 主要文件改动清单

后端新增：

- `backend/app/services/scoring_definition_service.py`
- 对应服务与 API 测试文件

后端修改：

- `backend/app/routers/system_settings.py`
- `backend/app/services/system_settings_service.py`
- `backend/app/services/render_quality_service.py`
- 测试任务和测试会话配置构建相关服务

前端新增：

- `frontend/src/components/ScoringDefinitionEditor/index.tsx`

前端修改：

- `frontend/src/pages/Settings/index.tsx`
- `frontend/src/api/systemSettings.ts`
- 渲染质量分析结果类型与展示组件

## 11. 后续扩展建议

在本期稳定运行后，可按真实测试数据逐步扩展：

1. 支持具名评分模板，并允许用户在启动测试前选择模板。
2. 支持按项目、设备类型或场景绑定评分模板。
3. 通过基准设备和专家标注数据校准扣分值与等级阈值。
4. 提供显式的历史结果重新计算功能，并保留原始评分。
5. 在具备版本管理、校准依据和回滚能力后，再考虑开放规则扣分与阈值编辑。

不要直接把所有扣分规则暴露给用户。评分模型的可配置性越高，越需要版本、审计、解释和校准数据，否则分数虽然可调，但难以保持可比性和科学性。
