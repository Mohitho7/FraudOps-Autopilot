import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import RecommendationCard from './RecommendationCard';

const recommendation = {
  case_id: 'CASE-2001',
  recommendation: 'ESCALATE' as const,
  confidence: 'HIGH' as const,
  investigation_summary: 'Multiple connected transactions need human review.',
  generated_at: '2026-09-30T10:30:25+05:30',
  reasons: [{ id: 'R-1', description: 'High transaction velocity', evidence_refs: ['E-01'] }],
};

describe('RecommendationCard', () => {
  it('renders advisory findings and evidence references', () => {
    render(<RecommendationCard recommendation={recommendation} />);

    expect(screen.getByRole('heading', { name: 'Agent Recommendation' })).toBeInTheDocument();
    expect(screen.getByText('ESCALATE')).toBeInTheDocument();
    expect(screen.getByText('High transaction velocity')).toBeInTheDocument();
    expect(screen.getByText('Evidence: E-01')).toBeInTheDocument();
    expect(screen.getByText(/Advisory findings for human review/)).toBeInTheDocument();
  });
});
