import apiClient from './client';
import type { TestSession } from './sessions';
import type { MetricCatalog, TestScope, TestScopeSummary } from '@/lib/testScope';

export interface UnityEngineResource {
  id: string;
  name: string;
  version: string;
  executable_path: string;
  enabled: boolean;
  is_default: boolean;
  exists: boolean;
  notes?: string | null;
}

export interface UnitySceneResource {
  id: string;
  name: string;
  description: string | null;
  project_path: string;
  scene_path: string;
  scene_file_path: string;
  enabled: boolean;
  is_default: boolean;
  exists: boolean;
  collector_package_name: string;
  collector_package_path: string | null;
  manifest_has_plugin: boolean;
  tags: string[];
}

export interface UnityQualityChecks {
  lighting: boolean;
  materials: boolean;
  post_processing: boolean;
  physics: boolean;
}

export interface UnityMetricChecks {
  frame_rate: boolean;
  frame_time: boolean;
  cpu: boolean;
  gpu: boolean;
  memory: boolean;
  device_info: boolean;
}

export interface UnityTestStartRequest {
  project_id: number;
  unity_engine_id: string;
  scene_resource_id: string;
  test_scope?: TestScope;
  quality_checks: UnityQualityChecks;
  quality_metric_checks?: Record<string, boolean>;
  metric_checks?: Partial<UnityMetricChecks>;
  collect_interval: number;
  frame_rate_duration_seconds: number;
  metrics_duration_seconds: number;
  batchmode: boolean;
  ensure_plugin: boolean;
}

export interface UnityTestTask {
  id: number;
  name: string;
  description: string | null;
  status: string;
  task_type: string;
  project_id: number | null;
  scene_id: number | null;
  config: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
}

export interface UnityTestStartResponse {
  task: UnityTestTask;
  session: TestSession;
  engine: UnityEngineResource;
  scene: UnitySceneResource;
  process_id: number | null;
  task_config_path: string;
  unity_log_path: string;
  runner_log_path: string;
}

export interface UnityTestStopResponse {
  task: UnityTestTask;
  session: TestSession | null;
}

export interface UnityTaskLogsResponse {
  task: UnityTestTask;
  session: TestSession | null;
  runner_log_path: string | null;
  unity_log_path: string | null;
  lines: string[];
}

export interface UnityRealtimeProgress {
  type: 'unity_progress';
  task_id: number;
  session_id: number;
  phase: string;
  phase_label: string;
  progress: number;
  remaining_seconds: number;
  sample_count: number;
  fps: number;
  frame_time_ms: number;
  raw_frame_time_ms: number;
  cpu_usage_percent: number;
  gpu_usage_percent: number;
  memory_mb: number;
  managed_memory_mb: number;
  graphics_memory_mb: number;
  system_memory_mb: number;
  draw_calls: number;
  triangles: number;
  vertices: number;
  active_light_count: number;
  realtime_light_count: number;
  shadow_caster_count: number;
  reflection_probe_count: number;
  material_count: number;
  unique_material_count: number;
  transparent_material_count: number;
  post_process_volume_count: number;
  render_texture_count: number;
  rigidbody_count: number;
  collider_count: number;
  is_xr_active: boolean;
  xr_device_name: string;
  device_model: string;
  operating_system: string;
  unity_version: string;
  graphics_device_name: string;
  render_pipeline: string;
  screen_resolution: string;
  received_at?: string;
  test_scope_version?: number;
  test_scope_summary?: TestScopeSummary;
  selected_metric_ids?: string[];
  skipped_metric_ids?: string[];
}

export function createUnityProgressWebSocket(taskId: number): WebSocket {
  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const baseUrl = new URL(apiBase, window.location.origin);
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  baseUrl.pathname = `${baseUrl.pathname.replace(/\/$/, '')}/unity-runner/progress/${taskId}/ws`;
  baseUrl.search = `token=${encodeURIComponent(localStorage.getItem('xr_token') || '')}`;
  return new WebSocket(baseUrl);
}

export const unityRunnerApi = {
  getTestMetricsCatalog: async (): Promise<MetricCatalog> => {
    const response = await apiClient.get<MetricCatalog>('/unity-runner/test-metrics/catalog');
    return response.data;
  },

  getDefaultTestScope: async (): Promise<{ default_scope: TestScope; scope_summary: TestScopeSummary }> => {
    const response = await apiClient.get<{ default_scope: TestScope; scope_summary: TestScopeSummary }>(
      '/unity-runner/test-metrics/default-scope',
    );
    return response.data;
  },

  listEngines: async (): Promise<UnityEngineResource[]> => {
    const response = await apiClient.get<{ items: UnityEngineResource[] }>('/unity-runner/engines');
    return response.data.items;
  },

  listScenes: async (params?: { project_id?: number }): Promise<UnitySceneResource[]> => {
    const response = await apiClient.get<{ items: UnitySceneResource[] }>('/unity-runner/scenes', { params });
    return response.data.items;
  },

  startTest: async (data: UnityTestStartRequest): Promise<UnityTestStartResponse> => {
    const response = await apiClient.post<UnityTestStartResponse>('/unity-runner/test-tasks/start', data);
    return response.data;
  },

  stopTest: async (taskId: number): Promise<UnityTestStopResponse> => {
    const response = await apiClient.post<UnityTestStopResponse>(`/unity-runner/test-tasks/${taskId}/stop`);
    return response.data;
  },

  getTaskLogs: async (taskId: number, params?: { tail_lines?: number }): Promise<UnityTaskLogsResponse> => {
    const response = await apiClient.get<UnityTaskLogsResponse>(`/unity-runner/test-tasks/${taskId}/logs`, { params });
    return response.data;
  },

  getLatestProgress: async (taskId: number): Promise<UnityRealtimeProgress | null> => {
    const response = await apiClient.get<{ item: UnityRealtimeProgress | null }>(`/unity-runner/progress/${taskId}/latest`);
    return response.data.item;
  },
};
