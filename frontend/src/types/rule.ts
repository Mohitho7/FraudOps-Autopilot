export interface RuleResult {
  rule_id: string;
  rule_name: string;
  description: string;
  triggered: boolean;
  score_impact?: number;
  severity?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  reason?: string;
  evidence_values?: Record<string, string | number | boolean>;
}

export interface FraudRule {
  id: string;
  name: string;
  description: string;
  category: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'ACTIVE' | 'INACTIVE';
  updated_at: string;
}

export interface RuleSimulationInput {
  amount: number;
  customer: string;
  merchant: string;
  location: string;
  transaction_count: number;
  time_interval_minutes: number;
  device: string;
}

export interface RuleSimulationResult {
  risk_score?: number;
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  triggered_rules: RuleResult[];
  non_triggered_rules: RuleResult[];
  factors: string[];
}
