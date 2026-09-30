/** Transaction types for FraudOps Autopilot */

export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type TransactionStatus = 
  | 'pending'
  | 'flagged'
  | 'under_review'
  | 'cleared'
  | 'confirmed_fraud'
  | 'escalated';

export interface Transaction {
  id: string;
  amount: number;
  currency: string;
  customer_id: string;
  customer_name: string;
  merchant_id: string;
  merchant_name: string;
  category: string;
  timestamp: string;
  risk_score: number;
  risk_level: RiskLevel;
  status: TransactionStatus;
  location?: string;
  rules_triggered?: number;
  transaction_type?: string;
  payment_method?: string;
  device_information?: string;
  ip_address?: string;
  case_id?: string;
  
  // Extended Context
  rule_results?: import('./rule').RuleResult[];
  customer_context?: import('./case').CustomerContext;
  merchant_context?: import('./case').MerchantContext;
  related_activity?: import('./case').RelatedActivity[];
  timeline?: import('./case').InvestigationEvent[];
  evidence?: import('./evidence').EvidenceItem[];
}

export interface TransactionFilters {
  search: string;
  risk_level: RiskLevel | 'ALL';
  status: TransactionStatus | 'ALL';
  sort_by: 'timestamp' | 'amount' | 'risk_score';
  sort_order: 'asc' | 'desc';
  page: number;
  limit: number;
}

export interface PaginatedTransactions {
  data: Transaction[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}
