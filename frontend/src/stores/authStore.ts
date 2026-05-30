import { create } from 'zustand';
import { authApi } from '@/api/auth';
import { LoginRequest, UserInfo } from '@/types';

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: UserInfo) => void;
  initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.login(credentials);
      localStorage.setItem('xr_token', response.access_token);
      localStorage.setItem('xr_user', JSON.stringify(response.user));
      set({
        token: response.access_token,
        user: response.user,
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
    localStorage.removeItem('xr_user');
    set({ token: null, user: null, isAuthenticated: false, error: null });
  },

  setUser: (user: UserInfo) => {
    set({ user });
  },

  initialize: () => {
    const token = localStorage.getItem('xr_token');
    const userStr = localStorage.getItem('xr_user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as UserInfo;
        set({ token, user, isAuthenticated: true });
      } catch {
        localStorage.removeItem('xr_token');
        localStorage.removeItem('xr_user');
      }
    }
  },
}));
