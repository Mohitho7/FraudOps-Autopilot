import type { RiskLevel } from './transaction';
import type { RuleResult } from './rule';
import type { EvidenceItem } from './evidence';

export type CaseStatus = 'open' | 'investigating' | 'review_required' | 'closed';

export interface InvestigationEvent {
  id: string;
  title: string;
  description: string;
  timestamp: string;
  status: 'completed' | 'current' | 'pending';
}

export interface CustomerContext {
  customer_id: string;
  customer_name: string;
  account_age_days?: number;
  typical_transaction_range?: string;
  recent_transaction_count_30d?: number;
  known_location?: string;
  device_information?: string;
}

export interface MerchantContext {
  merchant_id: string;
  merchant_name: string;
  category: string;
  location?: string;
  typical_transaction_amount?: string;
  transaction_frequency?: string;
}

export interface RelatedActivity {
  id: string;
  type: 'transaction' | 'case';
  description: string;
  date: string;
  relationship: string;
}

export interface FraudCase {
  id: string;
  transaction_id: string;
  customer_id: string;
  customer_name: string;
  merchant_id: string;
  merchant_name: string;
  amount: number;
  currency: string;
  risk_score: number;
  risk_level: RiskLevel;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  
  // Extended Context for Case Detail
  rule_results?: RuleResult[];
  customer_context?: CustomerContext;
  merchant_context?: MerchantContext;
  related_activity?: RelatedActivity[];
  timeline?: InvestigationEvent[];
  evidence?: EvidenceItem[];
}

export interface CaseFilters {
  search: string;
  risk_level: RiskLevel | 'ALL';
  status: CaseStatus | 'ALL';
  sort_by: 'created_at' | 'updated_at' | 'risk_score' | 'amount';
  sort_order: 'asc' | 'desc';
  page: number;
  limit: number;
}

export interface PaginatedCases {
  data: FraudCase[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}
