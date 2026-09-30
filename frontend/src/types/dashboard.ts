/** Dashboard types for FraudOps Autopilot */

export interface DashboardSummary {
  totalTransactions: number;
  flaggedTransactions: number;
  criticalCases: number;
  openCases: number;
  highRiskTransactions: number;
  reviewedToday: number;
}

export interface RecentActivity {
  id: string;
  type: 'flag' | 'review' | 'escalation';
  description: string;
  timestamp: string;
}
