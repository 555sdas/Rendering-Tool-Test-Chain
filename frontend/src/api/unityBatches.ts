import apiClient from './client';
import type { TestScope } from '@/lib/testScope';
import type { UnityTestTask } from './unityRunner';

export interface BatchSceneStartRequest {
  scene_resource_id: string;
  test_scope?: TestScope;
  collect_interval: number;
  frame_rate_duration_seconds: number;
  metrics_duration_seconds: number;
}

export interface UnityBatchStartRequest {
  project_id: number;
  unity_engine_id: string;
  batchmode?: boolean;
  ensure_plugin?: boolean;
  scenes: BatchSceneStartRequest[];
}

export interface BatchItem {
  id: number;
  scene_index: number;
  scene_resource_id: string;
  scene_display_name: string;
  unity_scene_path: string;
  status: string;
  attempt_count: number;
  current_task_id: number | null;
  current_session_id: number | null;
  config: Record<string, unknown> | null;
  attempt_history: unknown[];
  error_message: string | null;
}

export interface BatchSummary {
  id: number;
  project_id: number;
  parent_task_id: number;
  status: string;
  current_scene_index: number;
  scene_total: number;
  result_summary: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  decision_version: number;
  run_mode: 'multi_scene';
}

export interface UnityBatchDetail {
  batch: BatchSummary;
  parent_task: UnityTestTask | null;
  items: BatchItem[];
  allowed_actions: string[];
  process_id: number | null;
  launch_mode: string | null;
  orchestration_config_path: string | null;
  runner_log_path: string | null;
  unity_log_path: string | null;
}

export interface UnityBatchDecisionRequest {
  action: 'retry' | 'skip' | 'abort';
  expected_item_id: number;
  expected_scene_index: number;
  decision_version: number;
}

export const unityBatchesApi = {
  list(params?: { project_id?: number; status?: string; skip?: number; limit?: number }) {
    return apiClient.get<{ total: number; items: BatchSummary[] }>('/unity-runner/test-batches', { params });
  },

  getActive(projectId: number) {
    return apiClient.get<{ item: UnityBatchDetail | null }>('/unity-runner/test-batches/active', {
      params: { project_id: projectId },
    });
  },

  get(batchId: number) {
    return apiClient.get<UnityBatchDetail>(`/unity-runner/test-batches/${batchId}`);
  },

  start(payload: UnityBatchStartRequest) {
    // Existing Editors may need up to 60 seconds to refresh and compile the
    // collector package before the backend can dispatch the orchestration.
    return apiClient.post<UnityBatchDetail>('/unity-runner/test-batches/start', payload, { timeout: 75000 });
  },

  applyDecision(batchId: number, payload: UnityBatchDecisionRequest) {
    return apiClient.post<UnityBatchDetail>(`/unity-runner/test-batches/${batchId}/decision`, payload);
  },

  stop(batchId: number) {
    return apiClient.post<UnityBatchDetail>(`/unity-runner/test-batches/${batchId}/stop`);
  },
};
