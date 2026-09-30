export type ApiErrorCategory =
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'API_NOT_CONFIGURED'
  | 'UNKNOWN_ERROR';

export class ApiClientError extends Error {
  constructor(
    public readonly category: ApiErrorCategory,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}
