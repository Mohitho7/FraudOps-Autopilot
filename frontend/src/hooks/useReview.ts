import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { reviewApi } from '../services/reviewApi';
import type { ReviewFilters, DecisionPayload } from '../types/review';

export const useRecommendation = (caseId: string) => {
  return useQuery({
    queryKey: ['recommendation', caseId],
    queryFn: () => reviewApi.getRecommendation(caseId),
    enabled: !!caseId,
  });
};

export const useReviewHistory = (filters: ReviewFilters) => {
  return useQuery({
    queryKey: ['reviews', filters],
    queryFn: () => reviewApi.getReviewHistory(filters),
  });
};

export const useSubmitDecision = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (payload: DecisionPayload) => reviewApi.submitDecision(payload),
    onSuccess: (_, variables) => {
      // Invalidate queries so UI updates
      queryClient.invalidateQueries({ queryKey: ['case', variables.case_id] });
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
    },
  });
};
