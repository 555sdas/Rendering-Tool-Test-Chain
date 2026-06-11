import apiClient from './client';
import type { TestSession } from './sessions';

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
  process_id: number;
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

export const unityRunnerApi = {
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
};
