import { ApiClientError } from '../types/api';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 10_000;

export class ApiNotConfiguredError extends ApiClientError {
  constructor() {
    super('API_NOT_CONFIGURED', 'This backend endpoint is not configured.');
    this.name = 'ApiNotConfiguredError';
  }
}

export class ApiError extends ApiClientError {
  constructor(status: number, statusText: string, message?: string) {
    super(
      status === 401 ? 'UNAUTHORIZED' :
        status === 403 ? 'FORBIDDEN' :
          status === 404 ? 'NOT_FOUND' :
            status >= 400 && status < 500 ? 'VALIDATION_ERROR' :
              status >= 500 ? 'SERVER_ERROR' : 'UNKNOWN_ERROR',
      message || `API request failed: ${status} ${statusText}`,
      status,
    );
    this.name = 'ApiError';
  }
}

function getAuthToken(): string | null {
  return localStorage.getItem('fraudops_token');
}

function buildUrl(endpoint: string, params?: Record<string, string>): string {
  if (!endpoint.trim()) throw new ApiNotConfiguredError();
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== '') url.searchParams.append(key, value);
  });
  return url.toString();
}

async function request<T>(method: string, endpoint: string, body?: unknown, params?: Record<string, string>): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const token = getAuthToken();
    const response = await fetch(buildUrl(endpoint, params), {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      let message: string | undefined;
      try {
        const errorBody = await response.json() as { detail?: string; message?: string };
        message = errorBody.detail || errorBody.message;
      } catch {
        // Preserve the status-based error when the backend does not return JSON.
      }
      throw new ApiError(response.status, response.statusText, message);
    }

    if (response.status === 204) return undefined as T;
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiClientError) throw error;
    if ((error instanceof DOMException && error.name === 'AbortError') || (error instanceof Error && error.name === 'AbortError')) {
      throw new ApiClientError('TIMEOUT', 'The backend request timed out.');
    }
    throw new ApiClientError('NETWORK_ERROR', 'The backend could not be reached.');
  } finally {
    window.clearTimeout(timeout);
  }
}

export const apiClient = {
  get: <T>(endpoint: string, params?: Record<string, string>) => request<T>('GET', endpoint, undefined, params),
  post: <T>(endpoint: string, body?: unknown) => request<T>('POST', endpoint, body),
  put: <T>(endpoint: string, body?: unknown) => request<T>('PUT', endpoint, body),
  patch: <T>(endpoint: string, body?: unknown) => request<T>('PATCH', endpoint, body),
  delete: <T>(endpoint: string) => request<T>('DELETE', endpoint),
};

export default apiClient;
