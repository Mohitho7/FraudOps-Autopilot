import type { RiskLevel } from './transaction';

export type DecisionAction = 'APPROVE' | 'REJECT' | 'ESCALATE';

export interface ReviewRecord {
  id: string;
  case_id: string;
  transaction_id: string;
  reviewer_id: string;
  reviewer_name: string;
  decision: DecisionAction;
  notes: string;
  timestamp: string;
  risk_level: RiskLevel;
  risk_score: number;
}

export interface DecisionPayload {
  case_id: string;
  decision: DecisionAction;
  notes: string;
}

export interface ReviewFilters {
  search: string;
  decision: DecisionAction | 'ALL';
  risk_level: RiskLevel | 'ALL';
  sort_by: 'timestamp' | 'risk_score';
  sort_order: 'asc' | 'desc';
  page: number;
  limit: number;
}

export interface PaginatedReviews {
  data: ReviewRecord[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}
