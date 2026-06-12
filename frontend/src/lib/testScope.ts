export type MetricScopeStatus = 'selected' | 'skipped' | 'unavailable' | 'pending';

export interface TestScope {
  schema_version: number;
  source?: string;
  basic_metrics: Record<string, boolean>;
  quality_categories: Record<string, boolean>;
  quality_metrics: Record<string, boolean>;
}

export interface MetricCatalogEntry {
  id: string;
  label: string;
  group: string;
  parent_id?: string | null;
  default_enabled?: boolean;
  description?: string;
}

export interface MetricCatalog {
  schema_version: number;
  basic_metrics: MetricCatalogEntry[];
  quality_categories: MetricCatalogEntry[];
  quality_metrics: MetricCatalogEntry[];
  labels: Record<string, string>;
}

export interface TestScopeSummary {
  selected_ids: string[];
  skipped_ids: string[];
  selected_labels: string[];
  skipped_labels: string[];
  selected_count: number;
  skipped_count: number;
}

const BASIC_METRIC_IDS = ['frame_rate', 'frame_time', 'cpu', 'gpu', 'memory', 'device_info'];
const QUALITY_CATEGORY_IDS = ['lighting', 'materials', 'post_processing', 'physics'];
const QUALITY_METRIC_IDS = [
  'lighting.active_lights',
  'lighting.realtime_lights',
  'lighting.shadow_casters',
  'lighting.reflection_probes',
  'lighting.exposure_artifacts',
  'materials.material_slots',
  'materials.unique_materials',
  'materials.transparent_materials',
  'materials.draw_calls',
  'materials.texture_memory',
  'post_processing.volumes',
  'post_processing.render_textures',
  'post_processing.render_texture_memory',
  'post_processing.gpu_frame_budget',
  'post_processing.warnings',
  'physics.rigidbodies',
  'physics.colliders',
  'physics.penetration',
  'physics.pose_latency',
  'physics.prediction_error',
  'physics.long_frames',
];

/** 与后端 METRIC_MEASUREMENT_META.default_enabled 保持一致 */
const DEFAULT_ENABLED_QUALITY_METRICS: Record<string, boolean> = {
  'lighting.active_lights': true,
  'lighting.realtime_lights': true,
  'lighting.shadow_casters': true,
  'lighting.reflection_probes': true,
  'lighting.exposure_artifacts': false,
  'materials.material_slots': true,
  'materials.unique_materials': true,
  'materials.transparent_materials': true,
  'materials.draw_calls': true,
  'materials.texture_memory': true,
  'post_processing.volumes': true,
  'post_processing.render_textures': true,
  'post_processing.render_texture_memory': true,
  'post_processing.gpu_frame_budget': true,
  'post_processing.warnings': true,
  'physics.rigidbodies': true,
  'physics.colliders': true,
  'physics.penetration': true,
  'physics.pose_latency': false,
  'physics.prediction_error': false,
  'physics.long_frames': true,
};

const FALLBACK_LABELS: Record<string, string> = {
  frame_rate: '帧率 FPS',
  frame_time: '帧时间',
  cpu: 'CPU 使用率',
  gpu: 'GPU 使用率',
  memory: '内存',
  device_info: '设备信息',
  lighting: '光照与阴影',
  materials: '材质与纹理',
  post_processing: '后处理',
  physics: '物理仿真',
  'lighting.active_lights': '活动光源数量',
  'lighting.realtime_lights': '实时光源数量',
  'lighting.shadow_casters': '阴影投射体数量',
  'lighting.reflection_probes': '反射探针数量',
  'lighting.exposure_artifacts': '曝光异常标记',
  'materials.material_slots': '材质槽数量',
  'materials.unique_materials': '去重材质数量',
  'materials.transparent_materials': '透明材质数量',
  'materials.draw_calls': 'Draw Call',
  'materials.texture_memory': '纹理内存',
  'post_processing.volumes': '后处理 Volume 数量',
  'post_processing.render_textures': 'RenderTexture 数量',
  'post_processing.render_texture_memory': 'RenderTexture 内存',
  'post_processing.gpu_frame_budget': 'GPU 帧预算压力',
  'post_processing.warnings': '后处理配置警告',
  'physics.rigidbodies': '刚体数量',
  'physics.colliders': '碰撞体数量',
  'physics.penetration': '碰撞体穿透（启发式）',
  'physics.pose_latency': '姿态延迟',
  'physics.prediction_error': '预测误差',
  'physics.long_frames': '物理导致长帧',
};

const FALLBACK_DESCRIPTIONS: Record<string, string> = {
  frame_rate: '每秒渲染的帧数，反映画面流畅度，数值越高通常越流畅。',
  frame_time: '单帧渲染耗时（毫秒），用于分析卡顿、掉帧与长帧，数值越低越好。',
  cpu: 'CPU 占用百分比，反映脚本逻辑、物理与主线程对性能的影响。',
  gpu: 'GPU 占用与渲染负载，反映着色、绘制与后处理对显卡的压力。',
  memory: '进程内存占用（含托管堆、显存等），用于发现内存峰值与泄漏风险。',
  device_info: '采集设备型号、XR 能力、分辨率与渲染管线等测试环境信息。',
  'lighting.active_lights': '统计场景中当前处于启用状态的光源（Light 组件）个数。',
  'lighting.realtime_lights': '统计场景中烘焙模式为「实时光照」且处于启用的光源个数。',
  'lighting.shadow_casters': '统计场景中开启阴影投射的渲染器（Renderer）数量，即会参与生成阴影的物体数。',
  'lighting.reflection_probes': '统计场景中反射探针（Reflection Probe）组件的数量。',
  'lighting.exposure_artifacts': '统计测试过程中出现的曝光相关异常，包括过曝帧、欠曝帧、光照闪烁及曝光波动等标记。',
  'materials.material_slots': '统计场景中所有可见物体挂载的材质槽位总数（同一物体多个材质会计入多次）。',
  'materials.unique_materials': '统计场景中实际使用到的不同材质（Material）资源种类数（按资源去重）。',
  'materials.transparent_materials': '统计场景中被判定为透明/半透明的材质槽位数量（如透明、玻璃、粒子类 Shader）。',
  'materials.draw_calls': '采集测试期间每帧提交给 GPU 的 Draw Call 次数，并汇总为平均值。',
  'materials.texture_memory': '采集测试期间纹理资源占用的内存/显存用量，并记录峰值（MB）。',
  'post_processing.volumes': '统计场景中后处理 Volume 组件数量（用于控制景深、Bloom 等全屏特效的作用范围）。',
  'post_processing.render_textures': '统计场景中 RenderTexture（渲染纹理）资源的数量，常用于离屏渲染与特效。',
  'post_processing.render_texture_memory': '采集测试期间 RenderTexture 占用的内存峰值（MB）。',
  'post_processing.gpu_frame_budget': '根据测试期间的 GPU 占用与帧时间数据，评估渲染是否接近单帧 GPU 时间预算上限。',
  'post_processing.warnings': '审计启用的后处理 Volume 配置，统计缺少共享 Profile 的配置警告数量。',
  'physics.rigidbodies': '统计场景中刚体（Rigidbody）组件的数量。',
  'physics.colliders': '统计场景中碰撞体（Collider）组件的数量。',
  'physics.penetration': '启发式扫描最多 200 个活动非 Trigger 碰撞体，统计实际穿透的碰撞体对数量。',
  'physics.pose_latency': '采集 XR 设备姿态输入到画面更新之间的延迟时间（毫秒），并计算平均值。',
  'physics.prediction_error': '采集姿态预测值与实际姿态之间的误差（毫秒），并计算平均值。',
  'physics.long_frames': '统计测试过程中单帧耗时超过 33ms 的长帧出现次数。',
};

export function getMetricDescription(metricId: string, catalog?: MetricCatalog | null): string | undefined {
  if (catalog) {
    for (const entry of [...catalog.basic_metrics, ...catalog.quality_metrics]) {
      if (entry.id === metricId && entry.description) {
        return entry.description;
      }
    }
  }
  return FALLBACK_DESCRIPTIONS[metricId];
}

export function buildBuiltinDefaultScope(source = 'built_in_default'): TestScope {
  return {
    schema_version: 1,
    source,
    basic_metrics: Object.fromEntries(BASIC_METRIC_IDS.map((id) => [id, true])),
    quality_categories: Object.fromEntries(QUALITY_CATEGORY_IDS.map((id) => [id, true])),
    quality_metrics: Object.fromEntries(
      QUALITY_METRIC_IDS.map((id) => [id, DEFAULT_ENABLED_QUALITY_METRICS[id] ?? true]),
    ),
  };
}

export function fillScopeKeys(raw: Partial<TestScope> | null | undefined, source?: string): TestScope {
  const scope = buildBuiltinDefaultScope(source || raw?.source || 'built_in_default');
  if (!raw) return scope;
  scope.schema_version = raw.schema_version || 1;
  scope.source = source || raw.source || scope.source;
  for (const [section, ids] of [
    ['basic_metrics', BASIC_METRIC_IDS],
    ['quality_categories', QUALITY_CATEGORY_IDS],
    ['quality_metrics', QUALITY_METRIC_IDS],
  ] as const) {
    const incoming = raw[section] || {};
    for (const id of ids) {
      if (id in incoming) {
        scope[section][id] = Boolean(incoming[id]);
      }
    }
  }
  return applyParentRules(scope);
}

export function inferScopeFromSessionConfig(config: Record<string, unknown> | null | undefined): TestScope {
  if (!config) return buildBuiltinDefaultScope('legacy_inferred');
  const testScope = config.test_scope;
  if (testScope && typeof testScope === 'object') {
    return fillScopeKeys(testScope as Partial<TestScope>, (testScope as TestScope).source || 'session_snapshot');
  }
  const metricChecks = (config.metric_checks || config.metricChecks) as Record<string, boolean> | undefined;
  const qualityChecks = (config.quality_checks || config.qualityChecks) as Record<string, boolean> | undefined;
  const qualityMetricChecks = (config.quality_metric_checks || config.qualityMetricChecks) as Record<string, boolean> | undefined;
  if (metricChecks || qualityChecks || qualityMetricChecks) {
    const scope = buildBuiltinDefaultScope('legacy_inferred');
    if (metricChecks) {
      for (const id of BASIC_METRIC_IDS) {
        if (id in metricChecks) scope.basic_metrics[id] = Boolean(metricChecks[id]);
      }
    }
    if (qualityChecks) {
      const mapping: Record<string, string> = {
        lighting: 'lighting',
        materials: 'materials',
        material: 'materials',
        post_processing: 'post_processing',
        postProcessing: 'post_processing',
        physics: 'physics',
      };
      for (const [rawKey, normalized] of Object.entries(mapping)) {
        if (rawKey in qualityChecks) scope.quality_categories[normalized] = Boolean(qualityChecks[rawKey]);
      }
    }
    if (qualityMetricChecks) {
      for (const id of QUALITY_METRIC_IDS) {
        if (id in qualityMetricChecks) scope.quality_metrics[id] = Boolean(qualityMetricChecks[id]);
      }
    }
    return applyParentRules(scope);
  }
  return buildBuiltinDefaultScope('legacy_inferred');
}

export function applyParentRules(scope: TestScope): TestScope {
  const next = { ...scope, basic_metrics: { ...scope.basic_metrics }, quality_categories: { ...scope.quality_categories }, quality_metrics: { ...scope.quality_metrics } };
  for (const categoryId of QUALITY_CATEGORY_IDS) {
    const childKeys = QUALITY_METRIC_IDS.filter((id) => id.startsWith(`${categoryId}.`));
    if (!next.quality_categories[categoryId]) {
      for (const childKey of childKeys) next.quality_metrics[childKey] = false;
      continue;
    }
    if (childKeys.length > 0 && !childKeys.some((childKey) => next.quality_metrics[childKey])) {
      next.quality_categories[categoryId] = false;
      for (const childKey of childKeys) next.quality_metrics[childKey] = false;
    }
  }
  return next;
}

export function getEnabledLeafIds(scope: TestScope): string[] {
  const enabled: string[] = [];
  for (const id of BASIC_METRIC_IDS) {
    if (scope.basic_metrics[id]) enabled.push(id);
  }
  for (const id of QUALITY_METRIC_IDS) {
    const parent = id.split('.')[0];
    if (scope.quality_categories[parent] && scope.quality_metrics[id]) enabled.push(id);
  }
  return enabled;
}

export function buildScopeSummary(scope: TestScope, catalog?: MetricCatalog | null): TestScopeSummary {
  const selected_ids = getEnabledLeafIds(scope);
  const allLeafIds = [...BASIC_METRIC_IDS, ...QUALITY_METRIC_IDS];
  const skipped_ids = allLeafIds.filter((id) => !selected_ids.includes(id));
  const labelMap = buildLabelMap(catalog);
  return {
    selected_ids,
    skipped_ids,
    selected_labels: selected_ids.map((id) => labelMap[id] || FALLBACK_LABELS[id] || id),
    skipped_labels: skipped_ids.map((id) => labelMap[id] || FALLBACK_LABELS[id] || id),
    selected_count: selected_ids.length,
    skipped_count: skipped_ids.length,
  };
}

export function isMetricEnabled(scope: TestScope | null | undefined, metricId: string): boolean {
  if (!scope) return true;
  if (BASIC_METRIC_IDS.includes(metricId)) return Boolean(scope.basic_metrics[metricId]);
  if (QUALITY_METRIC_IDS.includes(metricId)) {
    const parent = metricId.split('.')[0];
    return Boolean(scope.quality_categories[parent] && scope.quality_metrics[metricId]);
  }
  if (QUALITY_CATEGORY_IDS.includes(metricId)) return Boolean(scope.quality_categories[metricId]);
  return false;
}

export function hasAnyEnabledLeaf(scope: TestScope): boolean {
  return getEnabledLeafIds(scope).length > 0;
}

export function buildLabelMap(catalog?: MetricCatalog | null): Record<string, string> {
  const map: Record<string, string> = { ...FALLBACK_LABELS };
  if (!catalog) return map;
  for (const entry of [...catalog.basic_metrics, ...catalog.quality_categories, ...catalog.quality_metrics]) {
    map[entry.id] = entry.label;
  }
  return map;
}

export function toggleCategory(scope: TestScope, categoryId: string, enabled: boolean): TestScope {
  const next = fillScopeKeys(scope);
  next.quality_categories[categoryId] = enabled;
  const childKeys = QUALITY_METRIC_IDS.filter((id) => id.startsWith(`${categoryId}.`));
  for (const childKey of childKeys) next.quality_metrics[childKey] = enabled;
  return applyParentRules(next);
}

export function toggleQualityMetric(scope: TestScope, metricId: string, enabled: boolean): TestScope {
  const next = fillScopeKeys(scope);
  next.quality_metrics[metricId] = enabled;
  const parent = metricId.split('.')[0];
  if (enabled) next.quality_categories[parent] = true;
  return applyParentRules(next);
}

export const TOTAL_LEAF_METRIC_COUNT = BASIC_METRIC_IDS.length + QUALITY_METRIC_IDS.length;

export function setAllScopeMetrics(scope: TestScope, enabled: boolean): TestScope {
  const next = fillScopeKeys(scope);
  for (const id of BASIC_METRIC_IDS) next.basic_metrics[id] = enabled;
  for (const id of QUALITY_CATEGORY_IDS) next.quality_categories[id] = enabled;
  for (const id of QUALITY_METRIC_IDS) next.quality_metrics[id] = enabled;
  return applyParentRules(next);
}

export function getCategoryCheckState(scope: TestScope, categoryId: string): { checked: boolean; indeterminate: boolean } {
  const childKeys = QUALITY_METRIC_IDS.filter((id) => id.startsWith(`${categoryId}.`));
  const enabledChildren = childKeys.filter((id) => scope.quality_metrics[id]);
  if (enabledChildren.length === 0) return { checked: false, indeterminate: false };
  if (enabledChildren.length === childKeys.length) return { checked: true, indeterminate: false };
  return { checked: false, indeterminate: true };
}

export function isLegacyInferredScope(scope: TestScope | null | undefined): boolean {
  return scope?.source === 'legacy_inferred';
}

export interface ScopeMetricItem {
  id: string;
  label: string;
  enabled: boolean;
}

export interface ScopeDisplayGroup {
  id: string;
  label: string;
  items: ScopeMetricItem[];
  selectedCount: number;
  totalCount: number;
}

export function buildScopeDisplayGroups(scope: TestScope, catalog?: MetricCatalog | null): ScopeDisplayGroup[] {
  const labelMap = buildLabelMap(catalog);
  const groups: ScopeDisplayGroup[] = [];

  const basicItems = BASIC_METRIC_IDS.map((id) => ({
    id,
    label: labelMap[id] || id,
    enabled: Boolean(scope.basic_metrics[id]),
  }));
  groups.push({
    id: 'basic_metric',
    label: catalog?.labels?.basic_metric || '基础性能指标',
    items: basicItems,
    selectedCount: basicItems.filter((item) => item.enabled).length,
    totalCount: basicItems.length,
  });

  for (const categoryId of QUALITY_CATEGORY_IDS) {
    const childIds = QUALITY_METRIC_IDS.filter((id) => id.startsWith(`${categoryId}.`));
    const items = childIds.map((id) => ({
      id,
      label: labelMap[id] || id,
      enabled: Boolean(scope.quality_categories[categoryId] && scope.quality_metrics[id]),
    }));
    groups.push({
      id: categoryId,
      label: labelMap[categoryId] || categoryId,
      items,
      selectedCount: items.filter((item) => item.enabled).length,
      totalCount: items.length,
    });
  }

  return groups;
}

export function formatScopeGroupStatus(group: ScopeDisplayGroup): string {
  if (group.selectedCount === 0) return '未纳入';
  if (group.selectedCount === group.totalCount) return `全部纳入 (${group.selectedCount}/${group.totalCount})`;
  return `${group.selectedCount}/${group.totalCount} 项已纳入`;
}
