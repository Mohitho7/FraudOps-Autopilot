/**
 * Auth API — Authentication service for FraudOps Autopilot
 * 
 * MOCK AUTHENTICATION: The backend auth API is not yet implemented.
 * This uses a temporary mock authentication flow to demonstrate the frontend.
 * 
 * To switch to real API: 
 *   - Replace the mock login() with: apiClient.post<AuthResponse>('/auth/login', credentials)
 *   - Remove the simulated delay and mock response
 */

import type { LoginCredentials, AuthResponse, Reviewer } from '../types/auth';
import apiClient from './apiClient';
import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';

// =============================================
// MOCK AUTH — Remove when backend is available
// =============================================
const MOCK_REVIEWER: Reviewer = {
  id: 'R-001',
  name: 'Alex Reviewer',
  email: 'alex.reviewer@fraudops.dev',
  role: 'reviewer',
};

const MOCK_CREDENTIALS = {
  email: 'alex@fraudops.dev',
  password: 'reviewer123',
};
// =============================================

export const authApi = {
  /**
   * MOCK: Authenticate a reviewer
   * Replace with: apiClient.post<AuthResponse>('/auth/login', credentials)
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    if (isEndpointConfigured(API_ENDPOINTS.auth.login)) {
      return apiClient.post<AuthResponse>(API_ENDPOINTS.auth.login, credentials);
    }
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 800));

    // Mock validation
    if (
      credentials.email === MOCK_CREDENTIALS.email &&
      credentials.password === MOCK_CREDENTIALS.password
    ) {
      return {
        token: 'mock-jwt-token-for-demo-only',
        reviewer: MOCK_REVIEWER,
      };
    }

    throw new Error('Invalid email or password');
  },

  /**
   * Get current reviewer info from stored session
   */
  getCurrentReviewer(): Reviewer | null {
    const stored = localStorage.getItem('fraudops_reviewer');
    if (stored) {
      try {
        return JSON.parse(stored) as Reviewer;
      } catch {
        return null;
      }
    }
    return MOCK_REVIEWER;
  },

  /**
   * Store session after successful login
   */
  setSession(authResponse: AuthResponse): void {
    localStorage.setItem('fraudops_token', authResponse.token);
    localStorage.setItem('fraudops_reviewer', JSON.stringify(authResponse.reviewer));
  },

  /**
   * Clear session on logout
   */
  clearSession(): void {
    localStorage.removeItem('fraudops_token');
    localStorage.removeItem('fraudops_reviewer');
  },

  /**
   * Check if a session exists
   */
  isAuthenticated(): boolean {
    return !!localStorage.getItem('fraudops_token');
  },
};

export default authApi;
