import type { FraudCase, CaseFilters, PaginatedCases } from '../types/case';
import { mockCases } from '../mocks/caseMock';
import apiClient from './apiClient';
import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';

export const caseApi = {
  /**
   * MOCK: Get paginated, filtered cases
   * Replace with: apiClient.get<PaginatedCases>('/cases', params)
   */
  async getCases(filters: CaseFilters): Promise<PaginatedCases> {
    if (isEndpointConfigured(API_ENDPOINTS.cases.list)) {
      return apiClient.get<PaginatedCases>(API_ENDPOINTS.cases.list, Object.fromEntries(Object.entries(filters).map(([key, value]) => [key, String(value)])));
    }
    await new Promise((resolve) => setTimeout(resolve, 500));

    let filtered = [...mockCases];

    if (filters.search) {
      const term = filters.search.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.id.toLowerCase().includes(term) ||
          c.transaction_id.toLowerCase().includes(term) ||
          c.customer_name.toLowerCase().includes(term) ||
          c.merchant_name.toLowerCase().includes(term)
      );
    }

    if (filters.risk_level !== 'ALL') {
      filtered = filtered.filter((c) => c.risk_level === filters.risk_level);
    }

    if (filters.status !== 'ALL') {
      filtered = filtered.filter((c) => c.status === filters.status);
    }

    filtered.sort((a, b) => {
      let comparison = 0;
      switch (filters.sort_by) {
        case 'amount':
          comparison = a.amount - b.amount;
          break;
        case 'risk_score':
          comparison = a.risk_score - b.risk_score;
          break;
        case 'updated_at':
          comparison = new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
          break;
        case 'created_at':
        default:
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
      }
      return filters.sort_order === 'desc' ? -comparison : comparison;
    });

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
   * Get a single case by ID
   * Documented endpoint: GET /cases/:id
   */
  async getCaseById(id: string): Promise<FraudCase | null> {
    if (isEndpointConfigured(API_ENDPOINTS.cases.detail)) {
      const endpoint = API_ENDPOINTS.cases.detail.replace(':id', id).replace('{id}', id);
      return apiClient.get<FraudCase>(endpoint);
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
    return mockCases.find((c) => c.id === id) || null;
  },
};

export default caseApi;
