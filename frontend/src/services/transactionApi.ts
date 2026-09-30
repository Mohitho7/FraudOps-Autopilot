/**
 * Transaction API — Transaction data service for FraudOps Autopilot
 * 
 * MOCK DATA: The backend API is not yet implemented.
 * Uses mock data from src/mocks/transactionMock.ts
 * 
 * To switch to real API:
 *   - Replace getTransactions() with: apiClient.get<PaginatedTransactions>('/transactions', params)
 *   - Remove the mock import, client-side filtering, and simulated delay
 */

import type { Transaction, TransactionFilters, PaginatedTransactions } from '../types/transaction';
import { mockTransactions } from '../mocks/transactionMock';
import apiClient from './apiClient';
import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';

export const transactionApi = {
  /**
   * MOCK: Get paginated, filtered transactions
   * Replace with: apiClient.get<PaginatedTransactions>('/transactions', params)
   * Documented endpoint: GET /transactions (doc07)
   * 
   * Note: Client-side filtering is used here only because mock data is local.
   * When the backend is available, filtering/sorting/pagination should be
   * handled server-side.
   */
  async getTransactions(filters: TransactionFilters): Promise<PaginatedTransactions> {
    if (isEndpointConfigured(API_ENDPOINTS.transactions.list)) {
      return apiClient.get<PaginatedTransactions>(API_ENDPOINTS.transactions.list, Object.fromEntries(Object.entries(filters).map(([key, value]) => [key, String(value)])));
    }
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 500));

    let filtered = [...mockTransactions];

    // Client-side search (mock only)
    if (filters.search) {
      const term = filters.search.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          t.id.toLowerCase().includes(term) ||
          t.customer_name.toLowerCase().includes(term) ||
          t.customer_id.toLowerCase().includes(term) ||
          t.merchant_name.toLowerCase().includes(term) ||
          t.merchant_id.toLowerCase().includes(term)
      );
    }

    // Client-side risk filter (mock only)
    if (filters.risk_level !== 'ALL') {
      filtered = filtered.filter((t) => t.risk_level === filters.risk_level);
    }

    // Client-side status filter (mock only)
    if (filters.status !== 'ALL') {
      filtered = filtered.filter((t) => t.status === filters.status);
    }

    // Client-side sorting (mock only)
    filtered.sort((a, b) => {
      let comparison = 0;
      switch (filters.sort_by) {
        case 'amount':
          comparison = a.amount - b.amount;
          break;
        case 'risk_score':
          comparison = a.risk_score - b.risk_score;
          break;
        case 'timestamp':
        default:
          comparison = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
      }
      return filters.sort_order === 'desc' ? -comparison : comparison;
    });

    // Client-side pagination (mock only)
    const total = filtered.length;
    const totalPages = Math.ceil(total / filters.limit);
    const start = (filters.page - 1) * filters.limit;
    const data = filtered.slice(start, start + filters.limit);

    return {
      data,
      total,
      page: filters.page,
      limit: filters.limit,
      totalPages,
    };
  },

  /**
   * Get a single transaction by ID
   * Documented endpoint: GET /transactions/:id (doc07)
   */
  async getTransactionById(id: string): Promise<Transaction | null> {
    if (isEndpointConfigured(API_ENDPOINTS.transactions.detail)) {
      const endpoint = API_ENDPOINTS.transactions.detail.replace(':id', id).replace('{id}', id);
      return apiClient.get<Transaction>(endpoint);
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
    return mockTransactions.find((t) => t.id === id) || null;
  },
};

export default transactionApi;
