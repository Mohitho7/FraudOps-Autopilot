import { useQuery } from '@tanstack/react-query';
import { networkApi } from '../services/networkApi';

export const useNetwork = (caseId?: string) => {
  return useQuery({
    queryKey: ['network', caseId || 'all'],
    queryFn: () => networkApi.getNetwork(caseId),
  });
};
