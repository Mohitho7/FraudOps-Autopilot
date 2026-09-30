import type { FraudCase, InvestigationEvent, CustomerContext, MerchantContext, RelatedActivity } from '../types/case';
import type { RuleResult } from '../types/rule';
import type { EvidenceItem } from '../types/evidence';

const mockRuleResults: RuleResult[] = [
  {
    rule_id: 'R-001',
    rule_name: 'High Transaction Velocity',
    description: 'Multiple transactions detected in a short time window.',
    triggered: true,
    score_impact: 45,
    severity: 'HIGH',
    reason: '5 transactions within 3 minutes',
  },
  {
    rule_id: 'R-002',
    rule_name: 'Geographic Inconsistency',
    description: 'Transaction location does not match known customer location.',
    triggered: true,
    score_impact: 35,
    severity: 'MEDIUM',
    reason: 'Device IP in London, User profile in Mumbai',
  },
  {
    rule_id: 'R-003',
    rule_name: 'Unusual Amount',
    description: 'Transaction amount exceeds typical range.',
    triggered: false,
    score_impact: 0,
    severity: 'LOW',
  }
];

const mockCustomerContext: CustomerContext = {
  customer_id: 'C-1028',
  customer_name: 'Rajesh Kumar',
  account_age_days: 1450,
  typical_transaction_range: '₹5,000 - ₹50,000',
  recent_transaction_count_30d: 42,
  known_location: 'Mumbai, MH',
  device_information: 'iPhone 13, iOS 17.2',
};

const mockMerchantContext: MerchantContext = {
  merchant_id: 'M-FUEL-019',
  merchant_name: 'PetroMax Fuels',
  category: 'fuel_station',
  location: 'Mumbai, MH',
  typical_transaction_amount: '₹2,000 - ₹10,000',
  transaction_frequency: 'High',
};

const mockRelatedActivity: RelatedActivity[] = [
  {
    id: 'TXN-10481',
    type: 'transaction',
    description: 'Payment to PetroMax Fuels',
    date: '2026-09-30T10:28:00+05:30',
    relationship: 'Same merchant, 2 mins ago',
  },
  {
    id: 'TXN-10475',
    type: 'transaction',
    description: 'Payment to Prime Properties Ltd',
    date: '2026-09-29T16:20:00+05:30',
    relationship: 'Same customer',
  }
];

const mockTimeline: InvestigationEvent[] = [
  {
    id: 'EVT-01',
    title: 'Transaction flagged',
    description: 'Transaction TXN-10482 exceeded risk threshold',
    timestamp: '2026-09-30T10:30:05+05:30',
    status: 'completed',
  },
  {
    id: 'EVT-02',
    title: 'Rule evaluated',
    description: 'Velocity rule triggered',
    timestamp: '2026-09-30T10:30:06+05:30',
    status: 'completed',
  },
  {
    id: 'EVT-03',
    title: 'Agent investigation started',
    description: 'Gathering related context',
    timestamp: '2026-09-30T10:30:08+05:30',
    status: 'completed',
  },
  {
    id: 'EVT-04',
    title: 'Evidence collected',
    description: 'Agent retrieved 2 related transactions',
    timestamp: '2026-09-30T10:30:15+05:30',
    status: 'completed',
  },
  {
    id: 'EVT-05',
    title: 'Investigation completed',
    description: 'Case requires human review',
    timestamp: '2026-09-30T10:30:20+05:30',
    status: 'completed',
  },
];

const mockEvidence: EvidenceItem[] = [
  {
    id: 'E-01',
    source: 'Rule Engine',
    type: 'behavioral_pattern',
    summary: '5 transactions occurred within 3 minutes',
    timestamp: '2026-09-30T10:30:06+05:30',
    severity: 'HIGH',
  },
  {
    id: 'E-02',
    source: 'Agent Investigation',
    type: 'geographic_information',
    summary: 'Agent identified a geographic inconsistency between device IP and customer profile.',
    timestamp: '2026-09-30T10:30:10+05:30',
    severity: 'MEDIUM',
  }
];

export const mockCases: FraudCase[] = [
  {
    id: 'CASE-2001',
    transaction_id: 'TXN-10482',
    customer_id: 'C-1028',
    customer_name: 'Rajesh Kumar',
    merchant_id: 'M-FUEL-019',
    merchant_name: 'PetroMax Fuels',
    amount: 8500000,
    currency: 'INR',
    risk_score: 94,
    risk_level: 'CRITICAL',
    status: 'review_required',
    created_at: '2026-09-30T10:30:05+05:30',
    updated_at: '2026-09-30T10:30:20+05:30',
    rule_results: mockRuleResults,
    customer_context: mockCustomerContext,
    merchant_context: mockMerchantContext,
    related_activity: mockRelatedActivity,
    timeline: mockTimeline,
    evidence: mockEvidence,
  },
  {
    id: 'CASE-2002',
    transaction_id: 'TXN-10481',
    customer_id: 'C-1045',
    customer_name: 'Priya Sharma',
    merchant_id: 'M-GOLD-007',
    merchant_name: 'Golden Heritage Jewellers',
    amount: 4100000,
    currency: 'INR',
    risk_score: 89,
    risk_level: 'HIGH',
    status: 'open',
    created_at: '2026-09-30T09:15:05+05:30',
    updated_at: '2026-09-30T09:15:20+05:30',
  }
];
