/**
 * Regula Health - API Client
 * Axios-based HTTP client with authentication
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config;

        // If 401 and we haven't already tried to refresh
        if (error.response?.status === 401 && originalRequest && !('_retry' in originalRequest)) {
          (originalRequest as any)._retry = true;

          const refreshToken = localStorage.getItem('refresh_token');
          if (refreshToken) {
            try {
              const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
                refresh_token: refreshToken,
              });

              const { access_token, refresh_token: new_refresh_token } = response.data;
              localStorage.setItem('access_token', access_token);
              localStorage.setItem('refresh_token', new_refresh_token);

              // Retry original request
              originalRequest.headers!.Authorization = `Bearer ${access_token}`;
              return this.client(originalRequest);
            } catch (refreshError) {
              // Refresh failed - logout
              localStorage.removeItem('access_token');
              localStorage.removeItem('refresh_token');
              window.location.href = '/login';
              return Promise.reject(refreshError);
            }
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // Authentication
  async register(data: any) {
    return this.client.post('/api/v1/auth/register', data);
  }

  async login(email: string, password: string) {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    return this.client.post('/api/v1/auth/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  }

  async getCurrentUser() {
    return this.client.get('/api/v1/auth/me');
  }

  // Claims
  async uploadEDI(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    return this.client.post('/api/v1/claims/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }

  async getClaims(filters?: any) {
    return this.client.get('/api/v1/claims', { params: filters });
  }

  async getClaim(id: string) {
    return this.client.get(`/api/v1/claims/${id}`);
  }

  // Analytics
  async getDashboardMetrics(days: number = 30) {
    return this.client.get('/api/v1/analytics/dashboard', {
      params: { days },
    });
  }

  async getPayerStats() {
    return this.client.get('/api/v1/analytics/payers');
  }

  // Health check
  async healthCheck() {
    return this.client.get('/health');
  }
}

export const apiClient = new ApiClient();
