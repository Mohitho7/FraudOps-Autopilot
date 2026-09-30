import type { AgentRecommendation } from '../types/recommendation';
import type { ReviewRecord } from '../types/review';

export const mockRecommendations: Record<string, AgentRecommendation> = {
  'CASE-2001': {
    case_id: 'CASE-2001',
    recommendation: 'ESCALATE',
    confidence: 'HIGH',
    investigation_summary: 'Agent identified severe geographic discrepancy combined with high transaction velocity mapping to multiple previous escalated cases. Recommendation is to escalate for manual review.',
    generated_at: '2026-09-30T10:30:25+05:30',
    reasons: [
      {
        id: 'R-1',
        description: 'High transaction velocity (5 txns in 3 mins)',
        evidence_refs: ['E-01'],
      },
      {
        id: 'R-2',
        description: 'Geographic discrepancy (Mumbai vs London)',
        evidence_refs: ['E-02'],
      },
      {
        id: 'R-3',
        description: 'Related transactions flagged previously',
        evidence_refs: [],
      }
    ]
  },
  'CASE-2002': {
    case_id: 'CASE-2002',
    recommendation: 'APPROVE',
    confidence: 'MEDIUM',
    investigation_summary: 'Transaction amount is high, but consistent with historical purchases at this merchant. No related fraudulent activity found.',
    generated_at: '2026-09-30T09:15:25+05:30',
    reasons: [
      {
        id: 'R-4',
        description: 'Consistent with historical purchases',
        evidence_refs: [],
      }
    ]
  }
};

// Start with some history
export let mockReviewHistory: ReviewRecord[] = [
  {
    id: 'REV-991',
    case_id: 'CASE-1055',
    transaction_id: 'TXN-0955',
    reviewer_id: 'R-001',
    reviewer_name: 'Alex Reviewer',
    decision: 'REJECT',
    notes: 'Confirmed unauthorized usage based on customer support call.',
    timestamp: '2026-09-29T14:20:00+05:30',
    risk_level: 'CRITICAL',
    risk_score: 98,
  },
  {
    id: 'REV-992',
    case_id: 'CASE-1056',
    transaction_id: 'TXN-0956',
    reviewer_id: 'R-002',
    reviewer_name: 'Sarah Analyst',
    decision: 'APPROVE',
    notes: 'Customer traveling, verified via secondary authentication.',
    timestamp: '2026-09-29T15:45:00+05:30',
    risk_level: 'MEDIUM',
    risk_score: 65,
  }
];

export const addReviewRecord = (record: ReviewRecord) => {
  mockReviewHistory = [record, ...mockReviewHistory];
};
