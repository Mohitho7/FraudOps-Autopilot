export interface RecommendationReason {
  id: string;
  description: string;
  evidence_refs: string[]; // IDs linking back to EvidenceItems
}

export interface AgentRecommendation {
  case_id: string;
  recommendation: 'APPROVE' | 'REJECT' | 'ESCALATE';
  confidence?: 'HIGH' | 'MEDIUM' | 'LOW';
  reasons: RecommendationReason[];
  investigation_summary: string;
  generated_at: string;
}
