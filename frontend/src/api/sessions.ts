import apiClient from './client';
import type { TestSession as UiTestSession } from '@/types';

export interface TestSession {
  id: number;
  name: string;
  scene_display_name?: string | null;
  description: string | null;
  status: UiTestSession['status'];
  device_model: string | null;
  os_version: string | null;
  xr_runtime: string | null;
  app_version: string | null;
  scene_id: number | null;
  user_id: number | null;
  project_id: number | null;
  config: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface TestSessionCreate {
  name: string;
  description?: string;
  device_model?: string;
  os_version?: string;
  xr_runtime?: string;
  app_version?: string;
  scene_id?: number;
  project_id?: number;
  config?: Record<string, unknown>;
}

export interface PerformanceSample {
  id: number;
  test_session_id: number;
  timestamp: string;
  frame_time_ms: number | null;
  fps: number | null;
  cpu_usage_percent: number | null;
  gpu_usage_percent: number | null;
  memory_mb: number | null;
  battery_level: number | null;
  battery_temperature: number | null;
  draw_calls: number | null;
  triangle_count: number | null;
  vertex_count: number | null;
  set_pass_calls: number | null;
  texture_memory_mb: number | null;
  mesh_memory_mb: number | null;
  render_texture_memory_mb: number | null;
  gc_collect_count: number | null;
  gc_allocated_mb: number | null;
  screen_resolution: string | null;
  tracking_state: string | null;
  prediction_error_ms: number | null;
  pose_latency_ms: number | null;
  extra_metrics: Record<string, unknown> | null;
}

export interface PerformanceSampleCreate {
  timestamp: string;
  frame_time_ms?: number;
  fps?: number;
  cpu_usage_percent?: number;
  gpu_usage_percent?: number;
  memory_mb?: number;
  battery_level?: number;
  battery_temperature?: number;
  draw_calls?: number;
  triangle_count?: number;
  vertex_count?: number;
  set_pass_calls?: number;
  texture_memory_mb?: number;
  mesh_memory_mb?: number;
  render_texture_memory_mb?: number;
  gc_collect_count?: number;
  gc_allocated_mb?: number;
  screen_resolution?: string;
  tracking_state?: string;
  prediction_error_ms?: number;
  pose_latency_ms?: number;
  extra_metrics?: Record<string, unknown>;
}

export const sessionsApi = {
  list: async (params?: { skip?: number; limit?: number; status?: string; project_id?: number }): Promise<{ total: number; items: TestSession[] }> => {
    const response = await apiClient.get<{ total: number; items: TestSession[] }>('/data-collection/test-sessions', { params });
    return response.data;
  },

  get: async (id: number): Promise<TestSession> => {
    const response = await apiClient.get<TestSession>(`/data-collection/test-sessions/${id}`);
    return response.data;
  },

  create: async (data: TestSessionCreate): Promise<TestSession> => {
    const response = await apiClient.post<TestSession>('/data-collection/test-sessions', data);
    return response.data;
  },

  start: async (id: number): Promise<TestSession> => {
    const response = await apiClient.post<TestSession>(`/data-collection/test-sessions/${id}/start`);
    return response.data;
  },

  stop: async (id: number, status?: string): Promise<TestSession> => {
    const response = await apiClient.post<TestSession>(`/data-collection/test-sessions/${id}/stop`, null, { params: { status } });
    return response.data;
  },

  addSample: async (sessionId: number, data: PerformanceSampleCreate): Promise<PerformanceSample> => {
    const response = await apiClient.post<PerformanceSample>(`/data-collection/test-sessions/${sessionId}/samples`, data);
    return response.data;
  },

  getSamples: async (sessionId: number, params?: { skip?: number; limit?: number }): Promise<PerformanceSample[]> => {
    const response = await apiClient.get<PerformanceSample[]>(`/data-collection/test-sessions/${sessionId}/samples`, { params });
    return response.data;
  },

  getStatistics: async (sessionId: number): Promise<Record<string, unknown>> => {
    const response = await apiClient.get<Record<string, unknown>>(`/data-collection/test-sessions/${sessionId}/statistics`);
    return response.data;
  },
};
