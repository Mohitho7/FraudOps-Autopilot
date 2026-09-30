/**
 * React Query hooks for dashboard data
 */

import { useQuery } from '@tanstack/react-query';
import dashboardApi from '../services/dashboardApi';

export const useDashboardSummary = () => {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => dashboardApi.getDashboardSummary(),
    staleTime: 30_000, // 30 seconds — dashboard data refreshes reasonably often
    retry: 2,
  });
};
