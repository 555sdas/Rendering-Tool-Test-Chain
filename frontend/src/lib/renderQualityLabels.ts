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
  penetration_event_count: '穿模/碰撞异常次数',
  avg_pose_latency_ms: '平均姿态延迟',
  avg_prediction_error_ms: '平均预测误差',
  long_frame_count: '长帧次数',
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
]);

export function getMetricLabel(key: string): string {
  return METRIC_LABELS[key] || key.replace(/_/g, ' ');
}

export function formatMetricValue(key: string, value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '-';
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) return String(value);

  if (PERCENT_KEYS.has(key)) return `${numeric.toFixed(1)}%`;
  if (MS_KEYS.has(key)) return `${numeric.toFixed(2)} ms`;
  if (MB_KEYS.has(key)) return `${numeric.toFixed(1)} MB`;
  if (COUNT_SUFFIX_KEYS.has(key)) return `${Math.round(numeric)}`;
  if (key.includes('count')) return `${Math.round(numeric)} 次`;
  return Number.isInteger(numeric) ? `${numeric}` : numeric.toFixed(2);
}

export interface MetricDisplayItem {
  key: string;
  label: string;
  value: string;
}

export function buildMetricDisplayItems(
  metrics: Record<string, number | string | null | undefined> | undefined,
): MetricDisplayItem[] {
  if (!metrics) return [];

  return Object.entries(metrics)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => ({
      key,
      label: getMetricLabel(key),
      value: formatMetricValue(key, value),
    }));
}

export function getStatusColor(status: string): string {
  if (status === '通过') return '#52c41a';
  if (status === '需关注') return '#faad14';
  if (status === '未测试') return '#d9d9d9';
  return '#ff4d4f';
}
