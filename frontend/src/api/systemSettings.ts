import apiClient from './client';

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

export const systemSettingsApi = {
  getUnitySettings: async (): Promise<UnitySettings> => {
    const response = await apiClient.get<UnitySettings>('/system-settings/unity');
    return response.data;
  },

  updateUnitySettings: async (data: UnitySettingsUpdate): Promise<UnitySettings> => {
    const response = await apiClient.put<UnitySettings>('/system-settings/unity', data);
    return response.data;
  },
};
