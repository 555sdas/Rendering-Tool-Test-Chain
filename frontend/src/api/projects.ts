import apiClient from './client';

export interface Project {
  id: number;
  name: string;
  description: string | null;
  project_type: string;
  status: string;
  created_by: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  project_type?: string;
  status?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  project_type?: string;
  status?: string;
}

export const projectsApi = {
  list: async (params?: { skip?: number; limit?: number; search?: string; status?: string }): Promise<Project[]> => {
    const response = await apiClient.get<Project[]>('/projects', { params });
    return response.data;
  },

  get: async (id: number): Promise<Project> => {
    const response = await apiClient.get<Project>(`/projects/${id}`);
    return response.data;
  },

  create: async (data: ProjectCreate): Promise<Project> => {
    const response = await apiClient.post<Project>('/projects', data);
    return response.data;
  },

  update: async (id: number, data: ProjectUpdate): Promise<Project> => {
    const response = await apiClient.put<Project>(`/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/projects/${id}`);
    return response.data;
  },
};
