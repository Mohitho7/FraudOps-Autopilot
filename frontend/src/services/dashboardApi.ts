/**
 * Dashboard API — Dashboard data service for FraudOps Autopilot
 * 
 * MOCK DATA: The backend API is not yet implemented.
 * Uses mock data from src/mocks/dashboardMock.ts
 * 
 * To switch to real API:
 *   - Replace getDashboardSummary() with: apiClient.get<DashboardSummary>('/dashboard/stats')
 *   - Remove the mock import and simulated delay
 */

import type { DashboardSummary } from '../types/dashboard';
import { mockDashboardSummary } from '../mocks/dashboardMock';
import apiClient from './apiClient';
import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';

export const dashboardApi = {
  /**
   * MOCK: Get dashboard summary metrics
   * Replace with: apiClient.get<DashboardSummary>('/dashboard/stats')
   * Documented endpoint: GET /dashboard/stats (doc07)
   */
  async getDashboardSummary(): Promise<DashboardSummary> {
    if (isEndpointConfigured(API_ENDPOINTS.dashboard.stats)) {
      return apiClient.get<DashboardSummary>(API_ENDPOINTS.dashboard.stats);
    }
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 600));
    return { ...mockDashboardSummary };
  },
};

export default dashboardApi;
