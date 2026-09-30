/** Authentication types for FraudOps Autopilot */

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface Reviewer {
  id: string;
  name: string;
  email: string;
  role: 'reviewer' | 'admin';
}

export interface AuthResponse {
  token: string;
  reviewer: Reviewer;
}

export interface AuthState {
  isAuthenticated: boolean;
  reviewer: Reviewer | null;
  token: string | null;
}
