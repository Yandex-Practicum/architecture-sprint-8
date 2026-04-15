// src/services/api.ts
import axios, { AxiosInstance, AxiosError } from 'axios';
import { SessionResponse, LoginUrlResponse } from '../types';

const API_URL = 'https://api.bio-pro.local:444/api';

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Важно для cookies между субдоменами
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Request interceptor для логирования
api.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// Response interceptor для обработки ошибок
api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.config.url} - ${response.status}`);
    return response;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      console.warn('[Auth] Session expired, redirecting to login');
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// API методы
export const getLoginUrl = async (idpHint: string | null = null): Promise<string> => {
  const params = new URLSearchParams();
  if (idpHint) params.append('idpHint', idpHint);
  const response = await api.get<LoginUrlResponse>(`/auth/login-url?${params.toString()}`);
  return response.data.url;
};

export const checkSession = async (): Promise<SessionResponse> => {
  const response = await api.get<SessionResponse>('/auth/session');
  return response.data;
};

export const logout = async (): Promise<string> => {
   try {
    const response = await api.post('/auth/logout');
    const { logoutUrl } = response.data;
    
    if (logoutUrl) {
      return logoutUrl;
    } else {
      return '/login';
    }
  } catch (error) {
    console.error('Logout failed:', error);
    return '/login';
  }
};

export default api;