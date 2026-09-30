/**
 * MOCK DATA — Dashboard Summary
 * 
 * This file provides mock data while the backend API is not yet available.
 * Replace with real API calls in dashboardApi.ts when backend is ready.
 * 
 * To switch to real API: update dashboardApi.ts to call GET /dashboard/stats
 * instead of importing from this file.
 */

import type { DashboardSummary } from '../types/dashboard';

export const mockDashboardSummary: DashboardSummary = {
  totalTransactions: 12450,
  flaggedTransactions: 87,
  criticalCases: 7,
  openCases: 12,
  highRiskTransactions: 23,
  reviewedToday: 15,
};
