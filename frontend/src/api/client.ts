import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ApiError, LoginResponse } from '@/types';
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
    const isAuthRequest = config.url?.includes('/auth/login') || config.url?.includes('/auth/refresh');
    if (token && config.headers && !isAuthRequest) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

type RetryableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let refreshPromise: Promise<string | null> | null = null;

function clearLocalAuth(): void {
  localStorage.removeItem('xr_token');
  localStorage.removeItem('xr_refresh_token');
  localStorage.removeItem('xr_user');
  useAuthStore.setState({ token: null, user: null, isAuthenticated: false, error: null });
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('xr_refresh_token');
  if (!refreshToken) return null;

  try {
    // 使用无拦截器客户端，避免刷新请求再次进入普通 401 重放链路。
    const response = await axios.post<LoginResponse>(
      `${API_BASE_URL}/auth/refresh`,
      { refresh_token: refreshToken },
      { timeout: 30000 },
    );
    localStorage.setItem('xr_token', response.data.access_token);
    localStorage.setItem('xr_refresh_token', response.data.refresh_token);
    useAuthStore.setState({
      token: response.data.access_token,
      isAuthenticated: true,
      error: null,
    });
    return response.data.access_token;
  } catch {
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    if (error.response) {
      const status = error.response.status;
      const message = error.response.data?.detail || '请求失败';

      if (status === 401) {
        const isRefreshRequest = error.config?.url?.includes('/auth/refresh');
        const requestConfig = error.config as RetryableRequestConfig | undefined;

        if (!isRefreshRequest && requestConfig && !requestConfig._retry) {
          requestConfig._retry = true;

          // 多个并发 401 请求共享同一个刷新 Promise，并直接获得同一枚新 token。
          if (!refreshPromise) {
            refreshPromise = refreshAccessToken().finally(() => {
              refreshPromise = null;
            });
          }

          const newToken = await refreshPromise;
          if (newToken) {
            requestConfig.headers.Authorization = `Bearer ${newToken}`;
            return apiClient.request(requestConfig);
          }

          clearLocalAuth();
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
