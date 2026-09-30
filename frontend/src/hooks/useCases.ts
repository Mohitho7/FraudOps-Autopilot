import { useQuery } from '@tanstack/react-query';
import caseApi from '../services/caseApi';
import type { CaseFilters } from '../types/case';

export const useCases = (filters: CaseFilters) => {
  return useQuery({
    queryKey: ['cases', filters],
    queryFn: () => caseApi.getCases(filters),
    staleTime: 15_000,
    retry: 2,
  });
};

export const useCase = (id: string) => {
  return useQuery({
    queryKey: ['case', id],
    queryFn: () => caseApi.getCaseById(id),
    enabled: !!id,
    retry: 2,
  });
};
