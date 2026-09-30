export type ApiErrorCategory =
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
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

export const getUserFacingApiMessage = (error: unknown, fallback: string): string => {
  if (!(error instanceof ApiClientError)) return fallback;
  switch (error.category) {
    case 'UNAUTHORIZED': return 'Your session has expired. Please sign in again.';
    case 'FORBIDDEN': return 'You are not authorized to perform this action.';
    case 'NOT_FOUND': return 'The requested information could not be found.';
    case 'VALIDATION_ERROR': return 'Please check the submitted information.';
    case 'TIMEOUT': return 'The service took too long to respond. Please try again.';
    case 'NETWORK_ERROR': return 'Backend service is currently unavailable. Demo data is being shown.';
    case 'API_NOT_CONFIGURED': return 'Backend integration is not configured. Demo data is being shown.';
    case 'SERVER_ERROR': return 'The service encountered an unexpected error. Please try again.';
    default: return fallback;
  }
};
