export interface UserInfo {
  id: number;
  username: string;
  role: 'admin' | 'tester' | 'report_editor' | 'viewer';
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export interface Project {
  id: number;
  name: string;
  description: string | null;
  project_type: string;
  status: 'active' | 'archived' | 'draft';
  created_by: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  page: number;
  page_size: number;
}

export interface DeviceInfo {
  device_name: string;
  os_version: string;
  gpu_model: string;
  gpu_version?: string;
  gpu_memory_mb?: number;
  cpu_model: string;
  ram_gb: number;
  system_memory_mb?: number;
}

export interface SceneInfo {
  scene_name: string;
  complexity: 'low' | 'medium' | 'high';
  render_pipeline: string;
}

export interface TestSession {
  id: number;
  name: string;
  description: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused' | 'cancelled';
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
  // UI 展示用扩展字段（兼容旧 mock 数据）
  task_id?: number;
  task_name?: string;
  device_info?: DeviceInfo;
  scene_info?: SceneInfo;
  start_time?: string;
  end_time?: string | null;
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

export interface ApiError {
  detail: string;
  status_code: number;
}
