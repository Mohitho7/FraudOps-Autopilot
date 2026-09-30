import type { DecisionPayload, PaginatedReviews, ReviewFilters, ReviewRecord } from '../types/review';
import type { AgentRecommendation } from '../types/recommendation';
import { mockRecommendations, mockReviewHistory, addReviewRecord } from '../mocks/reviewMock';
import authApi from './authApi';
import { mockCases } from '../mocks/caseMock';
import apiClient from './apiClient';
import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';

export const reviewApi = {
  async getRecommendation(caseId: string): Promise<AgentRecommendation | null> {
    if (isEndpointConfigured(API_ENDPOINTS.review.recommendation)) {
      const endpoint = API_ENDPOINTS.review.recommendation.replace(':caseId', caseId).replace('{case_id}', caseId);
      return apiClient.get<AgentRecommendation>(endpoint);
    }
    await new Promise(resolve => setTimeout(resolve, 600));
    return mockRecommendations[caseId] || null;
  },

  async submitDecision(payload: DecisionPayload): Promise<void> {
    if (isEndpointConfigured(API_ENDPOINTS.review.decision)) {
      await apiClient.post<void>(API_ENDPOINTS.review.decision, payload);
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 800));
    
    // Simulate updating case status based on human decision
    const caseIndex = mockCases.findIndex(c => c.id === payload.case_id);
    if (caseIndex === -1) throw new Error('Case not found');
    
    if (mockReviewHistory.some(record => record.case_id === payload.case_id)) {
      throw new Error('Case already reviewed');
    }
    
    // Create new review record
    const reviewer = authApi.getCurrentReviewer();
    const newRecord: ReviewRecord = {
      id: `REV-${Math.floor(Math.random() * 10000)}`,
      case_id: payload.case_id,
      transaction_id: mockCases[caseIndex].transaction_id,
      reviewer_id: reviewer?.id || 'unknown',
      reviewer_name: reviewer?.name || 'Unknown Reviewer',
      decision: payload.decision,
      notes: payload.notes,
      timestamp: new Date().toISOString(),
      risk_level: mockCases[caseIndex].risk_level,
      risk_score: mockCases[caseIndex].risk_score,
    };
    
    addReviewRecord(newRecord);
    
    // Update case status locally for mock
    let newStatus: 'closed' | 'investigating' = 'closed';
    if (payload.decision === 'ESCALATE') newStatus = 'investigating';
    
    mockCases[caseIndex] = { ...mockCases[caseIndex], status: newStatus, updated_at: new Date().toISOString() };
  },

  async getReviewHistory(filters: ReviewFilters): Promise<PaginatedReviews> {
    if (isEndpointConfigured(API_ENDPOINTS.review.history)) {
      return apiClient.get<PaginatedReviews>(API_ENDPOINTS.review.history, Object.fromEntries(Object.entries(filters).map(([key, value]) => [key, String(value)])));
    }
    await new Promise(resolve => setTimeout(resolve, 500));
    
    let filtered = [...mockReviewHistory];

    if (filters.search) {
      const term = filters.search.toLowerCase();
      filtered = filtered.filter(
        r => r.case_id.toLowerCase().includes(term) || r.transaction_id.toLowerCase().includes(term)
      );
    }
    
    if (filters.decision !== 'ALL') {
      filtered = filtered.filter(r => r.decision === filters.decision);
    }
    
    if (filters.risk_level !== 'ALL') {
      filtered = filtered.filter(r => r.risk_level === filters.risk_level);
    }
    
    filtered.sort((a, b) => {
      let comparison = 0;
      if (filters.sort_by === 'risk_score') {
        comparison = a.risk_score - b.risk_score;
      } else {
        comparison = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
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
  }
};
