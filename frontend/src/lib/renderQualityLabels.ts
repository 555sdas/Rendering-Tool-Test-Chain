import type { QualityMetricStatusEntry, QualityMetricStatusValue } from '@/api/analysis';

const METRIC_DESCRIPTIONS: Record<string, string> = {
  light_count: '测试期间统计到的、场景中处于启用状态的光源（Light）数量峰值。',
  active_light_count: '测试期间统计到的、场景中处于启用状态的光源（Light）数量峰值。',
  scene_light_count: '场景快照中的光源数量，用于在缺少时序采集时作为参考依据。',
  realtime_light_count: '测试期间统计到的、烘焙模式为「实时光照」且启用的光源数量峰值。',
  shadow_caster_count: '测试期间统计到的、开启阴影投射的渲染器（Renderer）数量峰值。',
  reflection_probe_count: '测试期间统计到的反射探针（Reflection Probe）组件数量峰值。',
  exposure_delta: '测试期间画面曝光波动幅度的峰值，数值越大表示明暗变化越明显。',
  avg_gpu_usage_percent: '测试全程 GPU 占用率的平均值，反映显卡渲染负载水平。',
  avg_gpu: '测试全程 GPU 占用率的平均值，反映显卡渲染负载水平。',
  p95_frame_time_ms: '测试全程帧时间的第 95 百分位值（ms），表示较慢 5% 帧的耗时水平。',
  p95_frame_ms: '测试全程帧时间的第 95 百分位值（ms），表示较慢 5% 帧的耗时水平。',
  lighting_flicker_count: '测试期间检测到光照或阴影闪烁的标记次数，0 表示未检出。',
  overexposure_count: '测试期间检测到过曝画面的标记次数。',
  underexposure_count: '测试期间检测到欠曝画面的标记次数。',
  material_count: '测试期间统计到的材质槽位总数峰值（所有可见物体上挂载的材质引用数）。',
  unique_material_count: '测试期间场景中实际使用到的不同材质（Material）资源种类数峰值。',
  scene_texture_count: '场景快照中的贴图/材质相关规模参考值。',
  transparent_material_count: '测试期间统计到的透明或半透明材质槽位数量峰值。',
  avg_draw_calls: '测试全程每帧 Draw Call 数量的平均值，反映 GPU 绘制批次规模。',
  avg_set_pass_calls: '测试全程每帧 SetPass 调用次数的平均值，反映 Shader/材质切换频率。',
  peak_texture_memory_mb: '测试期间纹理资源占用内存的峰值（MB）。',
  post_process_volume_count: '测试期间统计到的后处理 Volume 组件数量峰值。',
  render_texture_count: '测试期间统计到的 RenderTexture 资源数量峰值。',
  peak_render_texture_memory_mb: '测试期间 RenderTexture 占用内存的峰值（MB）。',
  rigidbody_count: '测试期间统计到的 Rigidbody 刚体组件数量峰值。',
  collider_count: '测试期间统计到的 Collider 碰撞体组件数量峰值。',
  penetration_event_count: '启发式扫描最多 200 个活动非 Trigger 碰撞体，统计实际穿透的碰撞体对数量峰值。',
  avg_pose_latency_ms: '测试全程 XR 姿态输入到画面更新之间的平均延迟（毫秒）。',
  avg_prediction_error_ms: '测试全程姿态预测值与实际姿态之间的平均误差（毫秒）。',
  long_frame_count: '测试期间单帧耗时超过 33ms 的帧数，用于关联卡顿与长帧问题。',
  post_processing_warning_count: '审计启用的后处理 Volume 配置，统计缺少共享 Profile 的配置警告数量，0 表示未检出。',
  ssim: '与参考帧对比的结构相似度（SSIM），越接近 1 表示画面越一致。',
  psnr: '与参考帧对比的峰值信噪比（PSNR），数值越高表示差异越小。',
  delta_e: '与参考帧对比的色差（Delta E），数值越小表示色彩偏差越小。',
};

const METRIC_LABELS: Record<string, string> = {
  light_count: '活动光源数量',
  active_light_count: '活动光源数量',
  realtime_light_count: '实时光源数量',
  shadow_caster_count: '阴影投射体数量',
  reflection_probe_count: '反射探针数量',
  exposure_delta: '曝光波动幅度',
  avg_gpu_usage_percent: '平均 GPU 占用',
  avg_gpu: '平均 GPU 占用',
  p95_frame_time_ms: 'P95 帧时间',
  p95_frame_ms: 'P95 帧时间',
  lighting_flicker_count: '光照闪烁标记',
  overexposure_count: '过曝帧标记',
  underexposure_count: '欠曝帧标记',
  material_count: '材质槽数量',
  unique_material_count: '去重材质数量',
  transparent_material_count: '透明材质数量',
  avg_draw_calls: '平均 Draw Call',
  avg_set_pass_calls: '平均 SetPass',
  peak_texture_memory_mb: '峰值纹理内存',
  post_process_volume_count: '后处理 Volume 数量',
  render_texture_count: 'RenderTexture 数量',
  peak_render_texture_memory_mb: '峰值渲染纹理内存',
  rigidbody_count: '刚体数量',
  collider_count: '碰撞体数量',
  penetration_event_count: '碰撞体穿透数量',
  avg_pose_latency_ms: '平均姿态延迟',
  avg_prediction_error_ms: '平均预测误差',
  long_frame_count: '长帧次数',
  post_processing_warning_count: '后处理配置警告',
  ssim: 'SSIM 结构相似度',
  psnr: 'PSNR 峰值信噪比',
  delta_e: 'Delta E 色差',
  scene_light_count: '场景光源数量',
  scene_texture_count: '场景贴图数量',
};

const PERCENT_KEYS = new Set(['avg_gpu_usage_percent', 'avg_gpu', 'exposure_delta']);
const MS_KEYS = new Set(['p95_frame_time_ms', 'p95_frame_ms', 'avg_pose_latency_ms', 'avg_prediction_error_ms']);
const MB_KEYS = new Set(['peak_texture_memory_mb', 'peak_render_texture_memory_mb']);
const COUNT_SUFFIX_KEYS = new Set([
  'light_count',
  'active_light_count',
  'realtime_light_count',
  'shadow_caster_count',
  'reflection_probe_count',
  'material_count',
  'unique_material_count',
  'transparent_material_count',
  'post_process_volume_count',
  'render_texture_count',
  'rigidbody_count',
  'collider_count',
  'avg_draw_calls',
  'avg_set_pass_calls',
  'long_frame_count',
  'lighting_flicker_count',
  'overexposure_count',
  'underexposure_count',
  'penetration_event_count',
  'post_processing_warning_count',
]);

export function getMetricLabel(key: string): string {
  return METRIC_LABELS[key] || key.replace(/_/g, ' ');
}

export function getRenderQualityMetricDescription(key: string): string | undefined {
  return METRIC_DESCRIPTIONS[key];
}

export function formatMetricValue(
  key: string,
  value: number | string | null | undefined,
  options?: { missingLabel?: string },
): string {
  if (value === null || value === undefined || value === '') {
    return options?.missingLabel ?? '-';
  }
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) return String(value);

  if (PERCENT_KEYS.has(key)) return `${numeric.toFixed(1)}%`;
  if (MS_KEYS.has(key)) return `${numeric.toFixed(2)} ms`;
  if (MB_KEYS.has(key)) return `${numeric.toFixed(1)} MB`;
  if (COUNT_SUFFIX_KEYS.has(key)) return `${Math.round(numeric)}`;
  if (key.includes('count')) return `${Math.round(numeric)} 次`;
  return Number.isInteger(numeric) ? `${numeric}` : numeric.toFixed(2);
}

const SCOPE_METRIC_LABELS: Record<string, string> = {
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

const STATUS_VALUE_LABELS: Record<Exclude<QualityMetricStatusValue, 'available'>, string> = {
  skipped: '未纳入本次测试',
  unavailable: '当前环境不支持',
  missing: '暂无数据',
  failed: '采集失败',
};

export interface MetricDisplayItem {
  key: string;
  label: string;
  value: string;
  description?: string;
  missing?: boolean;
  status?: QualityMetricStatusValue;
  statusTooltip?: string;
  statusReason?: string;
}

function resolveStatusDisplay(
  status: QualityMetricStatusValue,
  valueKey: string,
  rawValue: number | string | null | undefined,
  reasonLabel?: string | null,
): Pick<MetricDisplayItem, 'value' | 'missing' | 'status' | 'statusTooltip' | 'statusReason'> {
  if (status === 'available') {
    const missing = rawValue === null || rawValue === undefined || rawValue === '';
    return {
      value: formatMetricValue(valueKey, rawValue, { missingLabel: '暂无数据' }),
      missing,
      status: missing ? 'missing' : 'available',
      statusTooltip: missing ? reasonLabel || STATUS_VALUE_LABELS.missing : undefined,
    };
  }

  return {
    value: STATUS_VALUE_LABELS[status],
    missing: true,
    status,
    statusTooltip: reasonLabel || undefined,
    statusReason: reasonLabel || undefined,
  };
}

export function buildMetricDisplayItems(
  metrics: Record<string, number | string | null | undefined> | undefined,
  options?: { includeMissing?: boolean; missingLabel?: string },
): MetricDisplayItem[] {
  if (!metrics) return [];

  const missingLabel = options?.missingLabel ?? '暂无数据';

  return Object.entries(metrics)
    .filter(([, value]) => options?.includeMissing || (value !== null && value !== undefined && value !== ''))
    .map(([key, value]) => ({
      key,
      label: getMetricLabel(key),
      value: formatMetricValue(key, value, { missingLabel }),
      description: getRenderQualityMetricDescription(key),
      missing: value === null || value === undefined || value === '',
    }));
}

export function buildCategoryMetricDisplayItems(
  metrics: Record<string, number | string | null | undefined> | undefined,
  metricStatus: Record<string, QualityMetricStatusEntry> | undefined,
): MetricDisplayItem[] {
  if (metricStatus && Object.keys(metricStatus).length > 0) {
    return Object.entries(metricStatus)
      .filter(([, entry]) => entry.status !== 'skipped')
      .map(([metricId, entry]) => {
        const valueKey = entry.value_keys?.[0] || metricId;
        const rawValue = metrics?.[valueKey];
        const display = resolveStatusDisplay(entry.status, valueKey, rawValue, entry.reason_label);
        return {
          key: metricId,
          label: SCOPE_METRIC_LABELS[metricId] || getMetricLabel(valueKey),
          description: getRenderQualityMetricDescription(valueKey),
          ...display,
        };
      });
  }

  return buildMetricDisplayItems(metrics, { includeMissing: true, missingLabel: '暂无数据' });
}

export function getStatusColor(status: string): string {
  if (status === '通过') return '#52c41a';
  if (status === '需关注') return '#faad14';
  if (status === '未测试') return '#d9d9d9';
  return '#ff4d4f';
}
