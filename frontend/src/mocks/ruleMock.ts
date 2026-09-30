import type { FraudRule, RuleSimulationResult } from '../types/rule';

export const mockRules: FraudRule[] = [
  { id: 'RULE-001', name: 'Transaction velocity', description: 'Flags unusually frequent transactions within a short interval.', category: 'Behavioral', severity: 'HIGH', status: 'ACTIVE', updated_at: '2026-09-28T08:00:00Z' },
  { id: 'RULE-002', name: 'Unusual transaction amount', description: 'Identifies amounts outside the customer or merchant baseline.', category: 'Amount', severity: 'HIGH', status: 'ACTIVE', updated_at: '2026-09-27T11:30:00Z' },
  { id: 'RULE-003', name: 'Impossible geographic location', description: 'Detects incompatible locations across recent activity.', category: 'Location', severity: 'CRITICAL', status: 'ACTIVE', updated_at: '2026-09-26T15:45:00Z' },
  { id: 'RULE-004', name: 'Merchant category mismatch', description: 'Returns the rule engine result for a merchant context check.', category: 'Business context', severity: 'MEDIUM', status: 'INACTIVE', updated_at: '2026-09-20T10:10:00Z' },
];

export const mockSimulationResult: RuleSimulationResult = {
  risk_score: 82,
  risk_level: 'HIGH',
  triggered_rules: [
    { rule_id: 'RULE-001', rule_name: 'Transaction velocity', description: 'High transaction velocity returned by the rule engine.', triggered: true, severity: 'HIGH', reason: 'Returned by simulation service.' },
    { rule_id: 'RULE-003', rule_name: 'Impossible geographic location', description: 'Geographic inconsistency returned by the rule engine.', triggered: true, severity: 'CRITICAL', reason: 'Returned by simulation service.' },
  ],
  non_triggered_rules: [
    { rule_id: 'RULE-004', rule_name: 'Merchant category mismatch', description: 'Merchant context check returned no trigger.', triggered: false, severity: 'MEDIUM' },
  ],
  factors: ['High transaction velocity', 'Geographic inconsistency'],
};