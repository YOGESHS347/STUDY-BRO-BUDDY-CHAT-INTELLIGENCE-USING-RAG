import { supabase } from './supabase';
import type { HealthStatus } from '../types/api';
import type { UserProfile } from '../types/auth';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

export class ApiClientError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.data = data;
  }
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async getAuthToken(): Promise<string | null> {
    try {
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token || null;
    } catch {
      return null;
    }
  }

  private async getAuthHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };

    const token = await this.getAuthToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const authHeaders = await this.getAuthHeaders();
    const headers = {
      ...authHeaders,
      ...(options.headers || {}),
    };

    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch (networkError) {
      throw new ApiClientError(
        'Unable to connect to backend server. Please check your connection.',
        0,
        networkError
      );
    }

    if (!response.ok) {
      let errorMessage = `Request failed with status ${response.status}`;
      let errorData: unknown = null;

      try {
        errorData = await response.json();
        if (errorData && typeof errorData === 'object') {
          const dict = errorData as Record<string, unknown>;
          if (dict.detail) {
            errorMessage = typeof dict.detail === 'string' ? dict.detail : JSON.stringify(dict.detail);
          } else if (dict.message) {
            errorMessage = String(dict.message);
          }
        }
      } catch {
        // Fallback to text status
      }

      throw new ApiClientError(errorMessage, response.status, errorData);
    }

    // Return empty object for 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    try {
      return (await response.json()) as T;
    } catch {
      return {} as T;
    }
  }

  get<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  post<T>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  }

  delete<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  /**
   * Uploads a file using XMLHttpRequest to track REAL upload progress.
   * Does NOT fabricate or fake progress percentages.
   */
  async uploadWithProgress<T>(
    endpoint: string,
    file: File,
    onProgress?: (percent: number, loaded: number, total: number) => void
  ): Promise<T> {
    const token = await this.getAuthToken();
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file, file.name);

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && event.total > 0) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress(percent, event.loaded, event.total);
          }
        };
      }

      xhr.open('POST', url, true);
      xhr.setRequestHeader('Accept', 'application/json');
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }

      xhr.onload = () => {
        let responseData: unknown = null;
        try {
          if (xhr.responseText) {
            responseData = JSON.parse(xhr.responseText);
          }
        } catch {
          responseData = null;
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(responseData as T);
        } else {
          let errorMessage = `Upload failed with status ${xhr.status}`;
          if (responseData && typeof responseData === 'object') {
            const dict = responseData as Record<string, unknown>;
            if (dict.detail) {
              errorMessage = typeof dict.detail === 'string' ? dict.detail : JSON.stringify(dict.detail);
            } else if (dict.message) {
              errorMessage = String(dict.message);
            }
          }
          reject(new ApiClientError(errorMessage, xhr.status, responseData));
        }
      };

      xhr.onerror = () => {
        reject(
          new ApiClientError(
            'Network error during upload. Please check your connection.',
            0
          )
        );
      };

      xhr.onabort = () => {
        reject(new ApiClientError('Upload was cancelled.', 0));
      };

      xhr.send(formData);
    });
  }

  /**
   * Securely streams and downloads a document via authenticated GET.
   * Extracts filename from Content-Disposition if present.
   */
  async downloadBlob(endpoint: string): Promise<{ blob: Blob; filename: string }> {
    const token = await this.getAuthToken();
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    const headers: Record<string, string> = {
      Accept: '*/*',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(url, { headers, method: 'GET' });
    } catch (networkError) {
      throw new ApiClientError(
        'Unable to connect to backend server for download.',
        0,
        networkError
      );
    }

    if (!response.ok) {
      let errorMessage = `Download failed with status ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData && typeof errorData === 'object') {
          const dict = errorData as Record<string, unknown>;
          if (dict.detail) {
            errorMessage = typeof dict.detail === 'string' ? dict.detail : JSON.stringify(dict.detail);
          }
        }
      } catch {
        // Fallback
      }
      throw new ApiClientError(errorMessage, response.status);
    }

    // Extract filename from Content-Disposition header if present
    let filename = 'document';
    const disposition = response.headers.get('Content-Disposition');
    if (disposition) {
      const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
      if (match && match[1]) {
        filename = decodeURIComponent(match[1]);
      }
    }

    const blob = await response.blob();
    return { blob, filename };
  }

  // Common API shortcuts
  getHealth(): Promise<HealthStatus> {
    return this.get<HealthStatus>('/api/v1/health');
  }

  getCurrentUserProfile(): Promise<UserProfile> {
    return this.get<UserProfile>('/api/v1/users/me');
  }
}

export const api = new ApiClient(API_BASE_URL);
