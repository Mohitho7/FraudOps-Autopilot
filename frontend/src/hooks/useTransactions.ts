/**
 * React Query hooks for transaction data
 */

import { useQuery } from '@tanstack/react-query';
import transactionApi from '../services/transactionApi';
import type { TransactionFilters } from '../types/transaction';

export const useTransactions = (filters: TransactionFilters) => {
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => transactionApi.getTransactions(filters),
    staleTime: 15_000, // 15 seconds — transaction data refreshes more frequently
    retry: 2,
  });
};

export const useTransaction = (id: string) => {
  return useQuery({
    queryKey: ['transaction', id],
    queryFn: () => transactionApi.getTransactionById(id),
    enabled: !!id,
    retry: 2,
  });
};
