import apiClient from './client';
import type { MetricCatalog, TestScope, TestScopeSummary } from '@/lib/testScope';

export interface UnitySettingsStatus {
  unity_executable_exists: boolean;
  unity_project_exists: boolean;
  unity_scene_exists: boolean;
  discovered_scene_count?: number;
  discovered_scenes?: string[];
  collector_package_exists: boolean;
}

export interface UnitySettings {
  unity_executable_path: string;
  unity_project_path: string;
  unity_scene_path: string;
  collector_package_path: string;
  status: UnitySettingsStatus;
  settings_file: string;
}

export interface UnitySettingsUpdate {
  unity_executable_path: string;
  unity_project_path: string;
  unity_scene_path?: string;
  collector_package_path: string;
}

export type ScoringCategoryId = 'lighting' | 'material' | 'post_processing' | 'physics';

export interface ScoringDefinition {
  schema_version: number;
  category_weights: Record<ScoringCategoryId, number>;
}

export interface ScoringCategoryCatalogEntry {
  id: ScoringCategoryId;
  label: string;
  description: string;
}

export interface ScoringDefinitionResponse {
  definition: ScoringDefinition;
  catalog: {
    categories: ScoringCategoryCatalogEntry[];
  };
  summary: {
    total_weight: number;
    is_default: boolean;
  };
  settings_file: string;
}

const DEFAULT_SCORING_DEFINITION: ScoringDefinition = {
  schema_version: 1,
  category_weights: {
    lighting: 25,
    material: 25,
    post_processing: 25,
    physics: 25,
  },
};

export const systemSettingsApi = {
  getUnitySettings: async (): Promise<UnitySettings> => {
    const response = await apiClient.get<UnitySettings>('/system-settings/unity');
    return response.data;
  },

  updateUnitySettings: async (data: UnitySettingsUpdate): Promise<UnitySettings> => {
    const response = await apiClient.put<UnitySettings>('/system-settings/unity', data);
    return response.data;
  },

  getTestMetricsCatalog: async (): Promise<MetricCatalog> => {
    const response = await apiClient.get<MetricCatalog>('/system-settings/test-metrics/catalog');
    return response.data;
  },

  getDefaultTestScope: async (): Promise<{ default_scope: TestScope; scope_summary: TestScopeSummary }> => {
    const response = await apiClient.get<{ default_scope: TestScope; scope_summary: TestScopeSummary }>(
      '/system-settings/test-metrics',
    );
    return response.data;
  },

  updateDefaultTestScope: async (scope: TestScope): Promise<{ default_scope: TestScope; scope_summary: TestScopeSummary }> => {
    const response = await apiClient.put<{ default_scope: TestScope; scope_summary: TestScopeSummary }>(
      '/system-settings/test-metrics',
      scope,
    );
    return response.data;
  },

  resetDefaultTestScope: async (): Promise<{ default_scope: TestScope; scope_summary: TestScopeSummary }> => {
    const response = await apiClient.post<{ default_scope: TestScope; scope_summary: TestScopeSummary }>(
      '/system-settings/test-metrics/reset',
    );
    return response.data;
  },

  getScoringDefinition: async (): Promise<ScoringDefinitionResponse> => {
    const response = await apiClient.get<ScoringDefinitionResponse>('/system-settings/scoring-definition');
    return response.data;
  },

  updateScoringDefinition: async (definition: ScoringDefinition): Promise<ScoringDefinitionResponse> => {
    const response = await apiClient.put<ScoringDefinitionResponse>('/system-settings/scoring-definition', definition);
    return response.data;
  },

  resetScoringDefinition: async (): Promise<ScoringDefinitionResponse> => {
    const response = await apiClient.post<ScoringDefinitionResponse>('/system-settings/scoring-definition/reset');
    return response.data;
  },
};

export { DEFAULT_SCORING_DEFINITION };
