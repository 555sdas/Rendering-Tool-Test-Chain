import { create } from 'zustand';
import { authApi } from '@/api/auth';
import { LoginRequest, UserInfo } from '@/types';

function loadAuthFromStorage(): { token: string | null; user: UserInfo | null } {
  const token = localStorage.getItem('xr_token');
  const userStr = localStorage.getItem('xr_user');
  if (!token) {
    return { token: null, user: null };
  }

  if (userStr && userStr !== 'undefined' && userStr !== 'null') {
    try {
      return { token, user: JSON.parse(userStr) as UserInfo };
    } catch {
      localStorage.removeItem('xr_user');
    }
  }

  return { token, user: null };
}

const { token: savedToken, user: savedUser } = loadAuthFromStorage();

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<boolean>;
  setUser: (user: UserInfo) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: savedToken,
  user: savedUser,
  isAuthenticated: savedToken !== null,
  isLoading: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.login(credentials);
      localStorage.setItem('xr_token', response.access_token);
      localStorage.setItem('xr_refresh_token', response.refresh_token);
      if (response.user) {
        localStorage.setItem('xr_user', JSON.stringify(response.user));
      } else {
        localStorage.removeItem('xr_user');
      }
      set({
        token: response.access_token,
        user: response.user || null,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout errors
    }
    localStorage.removeItem('xr_token');
    localStorage.removeItem('xr_refresh_token');
    localStorage.removeItem('xr_user');
    set({ token: null, user: null, isAuthenticated: false, error: null });
  },

  refreshAuth: async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem('xr_refresh_token');
    if (!refreshToken) return false;

    try {
      const response = await authApi.refreshToken();
      localStorage.setItem('xr_token', response.access_token);
      localStorage.setItem('xr_refresh_token', response.refresh_token);
      if (response.user) {
        localStorage.setItem('xr_user', JSON.stringify(response.user));
      }
      set({
        token: response.access_token,
        user: response.user || get().user,
        isAuthenticated: true,
        error: null,
      });
      return true;
    } catch {
      // 刷新失败，保持当前状态（由调用方决定是否 logout）
      return false;
    }
  },

  setUser: (user: UserInfo) => {
    set({ user });
  },
}));
