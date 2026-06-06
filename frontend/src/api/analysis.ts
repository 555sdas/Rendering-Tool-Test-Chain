import apiClient from './client';

export interface FpsAnalysis {
  count: number;
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
  p1: number;
  p5: number;
  p95: number;
  p99: number;
  below_30_count: number;
  below_60_count: number;
  jank_count: number;
}

export interface FrameTimeAnalysis {
  count: number;
  mean_ms: number;
  median_ms: number;
  std_ms: number;
  min_ms: number;
  max_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  above_16_6ms_count: number;
  above_33_3ms_count: number;
}

export interface MemoryAnalysis {
  count: number;
  mean_mb: number;
  median_mb: number;
  min_mb: number;
  max_mb: number;
  std_mb: number;
  growth_rate_mb_per_min: number | null;
}

export interface ThermalAnalysis {
  count: number;
  mean_c: number;
  max_c: number;
  min_c: number;
  above_40_count: number;
  above_45_count: number;
}

export interface ThresholdViolation {
  rule_id: number;
  rule_name: string;
  metric_name: string;
  operator: string;
  threshold_value: number;
  actual_value: number;
  severity: string;
  sample_count: number;
}

export interface RenderQualityCategory {
  key: string;
  name: string;
  weight: number;
  score: number;
  status: string;
  metrics: Record<string, number | string | null>;
  deductions: Array<{
    points: number;
    reason: string;
  }>;
  recommendations: string[];
}

export interface RenderQualityAssessment {
  session_id: number;
  session_name: string;
  evaluation_mode: {
    type: string;
    description: string;
  };
  overall_score: number;
  grade: string;
  categories: RenderQualityCategory[];
  rubric: Record<string, string>;
  evidence: {
    sample_count: number;
    scene_asset: string | null;
    has_reference_frame_metrics: boolean;
    has_runtime_quality_metrics: boolean;
    note: string;
  };
}

export interface FullReport {
  session_info: {
    id: number;
    name: string;
    status: string;
    device_model: string | null;
    os_version: string | null;
    xr_runtime: string | null;
    app_version: string | null;
    config: Record<string, unknown> | null;
    started_at: string | null;
    ended_at: string | null;
    duration_seconds: number | null;
  };
  fps_analysis: FpsAnalysis;
  frame_time_analysis: FrameTimeAnalysis;
  memory_analysis: MemoryAnalysis;
  thermal_analysis: ThermalAnalysis;
  threshold_violations: ThresholdViolation[];
  stability_summary?: {
    sample_count: number;
    avg_fps: number | null;
    p95_frame_time_ms: number;
    p99_frame_time_ms: number;
    long_frame_count: number;
    dropped_frame_count: number;
    dropped_frame_rate: number;
    risk_level: string;
  };
  resource_summary?: {
    avg_draw_calls: number | null;
    avg_set_pass_calls: number | null;
    avg_triangle_count: number | null;
    peak_texture_memory_mb: number | null;
    peak_mesh_memory_mb: number | null;
    peak_render_texture_memory_mb: number | null;
    peak_gc_allocated_mb: number | null;
  };
  render_quality_assessment?: RenderQualityAssessment;
}

export interface TrendAnalysis {
  metric: string;
  session_count: number;
  sessions: Array<{
    session_id: number;
    session_name: string;
    mean: number;
    median: number;
    min: number;
    max: number;
    std: number;
  }>;
}

export const analysisApi = {
  getFpsAnalysis: async (sessionId: number): Promise<FpsAnalysis> => {
    const response = await apiClient.get<FpsAnalysis>(`/performance/analysis/${sessionId}/fps`);
    return response.data;
  },

  getFrameTimeAnalysis: async (sessionId: number): Promise<FrameTimeAnalysis> => {
    const response = await apiClient.get<FrameTimeAnalysis>(`/performance/analysis/${sessionId}/frame-time`);
    return response.data;
  },

  getMemoryAnalysis: async (sessionId: number): Promise<MemoryAnalysis> => {
    const response = await apiClient.get<MemoryAnalysis>(`/performance/analysis/${sessionId}/memory`);
    return response.data;
  },

  getThermalAnalysis: async (sessionId: number): Promise<ThermalAnalysis> => {
    const response = await apiClient.get<ThermalAnalysis>(`/performance/analysis/${sessionId}/thermal`);
    return response.data;
  },

  checkThresholds: async (sessionId: number, projectId?: number): Promise<ThresholdViolation[]> => {
    const response = await apiClient.get<ThresholdViolation[]>(`/performance/analysis/${sessionId}/thresholds`, {
      params: { project_id: projectId },
    });
    return response.data;
  },

  getFullReport: async (sessionId: number): Promise<FullReport> => {
    const response = await apiClient.get<FullReport>(`/performance/analysis/${sessionId}/full-report`);
    return response.data;
  },

  getRenderQualityAssessment: async (sessionId: number): Promise<RenderQualityAssessment> => {
    const response = await apiClient.get<RenderQualityAssessment>(`/performance/analysis/${sessionId}/render-quality`);
    return response.data;
  },

  getTrendAnalysis: async (sessionIds: number[], metric: string = 'fps'): Promise<TrendAnalysis> => {
    const response = await apiClient.get<TrendAnalysis>('/performance/trend', {
      params: { session_ids: sessionIds, metric },
    });
    return response.data;
  },
};
