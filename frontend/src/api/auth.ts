import apiClient from './client';
import { LoginRequest, LoginResponse, UserInfo } from '@/types';

export const authApi = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    const params = new URLSearchParams();
    params.append('username', credentials.username);
    params.append('password', credentials.password);
    const response = await apiClient.post<LoginResponse>('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  getCurrentUser: async (): Promise<UserInfo> => {
    const response = await apiClient.get<UserInfo>('/auth/me');
    return response.data;
  },

  refreshToken: async (): Promise<LoginResponse> => {
    const refreshToken = localStorage.getItem('xr_refresh_token');
    const response = await apiClient.post<LoginResponse>(
      '/auth/refresh',
      { refresh_token: refreshToken || '' },
    );
    return response.data;
  },
};
