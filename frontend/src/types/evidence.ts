export interface EvidenceItem {
  id: string;
  source: 'Transaction' | 'Customer History' | 'Merchant History' | 'Rule Engine' | 'Related Activity' | 'Agent Investigation';
  type: 'transaction_data' | 'rule_result' | 'historical_activity' | 'geographic_information' | 'behavioral_pattern';
  summary: string;
  timestamp?: string;
  severity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  details?: Record<string, string | number | boolean>;
}
