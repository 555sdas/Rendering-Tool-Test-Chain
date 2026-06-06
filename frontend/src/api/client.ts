import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ApiError } from '@/types';
import { useAuthStore } from '@/stores/authStore';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('xr_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

let refreshPromise: Promise<boolean> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    if (error.response) {
      const status = error.response.status;
      const message = error.response.data?.detail || '请求失败';

      if (status === 401) {
        const isRefreshRequest = error.config?.url?.includes('/auth/refresh');

        if (!isRefreshRequest) {
          // 多个并发 401 请求共享同一个刷新 Promise，避免竞态登出
          if (!refreshPromise) {
            refreshPromise = useAuthStore.getState().refreshAuth().finally(() => {
              refreshPromise = null;
            });
          }

          const refreshed = await refreshPromise;
          if (refreshed && error.config) {
            const newToken = localStorage.getItem('xr_token');
            if (newToken && error.config.headers) {
              error.config.headers.Authorization = `Bearer ${newToken}`;
            }
            return apiClient.request(error.config);
          }

          // 刷新失败 → 登出
          useAuthStore.getState().logout();
        }
      }

      return Promise.reject(new Error(message));
    }

    if (error.request) {
      return Promise.reject(new Error('网络错误，请检查连接'));
    }

    return Promise.reject(new Error('请求配置错误'));
  }
);

export default apiClient;
