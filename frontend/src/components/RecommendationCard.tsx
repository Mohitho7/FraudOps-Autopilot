import React from 'react';
import { Bot } from 'lucide-react';
import type { AgentRecommendation } from '../types/recommendation';

interface RecommendationCardProps {
  recommendation: AgentRecommendation;
}

const RecommendationCard: React.FC<RecommendationCardProps> = ({ recommendation }) => {
  return (
    <section className="bg-white border border-indigo-200 rounded-lg shadow-sm p-5" aria-labelledby="agent-recommendation-title">
      <div className="flex items-center space-x-3 mb-4">
        <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
          <Bot className="w-5 h-5" />
        </div>
        <div>
          <h3 id="agent-recommendation-title" className="text-sm font-semibold text-slate-800">Agent Recommendation</h3>
          <p className="text-xs text-slate-500">Advisory findings for human review</p>
        </div>
      </div>
      
      <div className="flex items-baseline space-x-4 mb-4">
        <div className="text-xl font-bold text-slate-900 capitalize">
          {recommendation.recommendation}
        </div>
        <div className="text-sm">
          <span className="text-slate-500">Confidence:</span>{' '}
          <span className="font-semibold text-slate-700">{recommendation.confidence || 'Not provided'}</span>
        </div>
      </div>
      
      <div className="bg-gray-50 border border-gray-100 rounded p-3 text-sm text-slate-700">
        <span className="font-medium text-slate-800 mb-1 block">Investigation summary</span>
        {recommendation.investigation_summary}
      </div>
      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Key findings</h4>
        <ol className="mt-2 space-y-2 text-sm text-slate-700">
          {recommendation.reasons.map((reason) => (
            <li key={reason.id} className="border-l-2 border-indigo-200 pl-3">
              <p>{reason.description}</p>
              {reason.evidence_refs.length > 0 && <p className="mt-1 text-xs text-slate-500">Evidence: {reason.evidence_refs.join(', ')}</p>}
            </li>
          ))}
        </ol>
      </div>
      <p className="mt-4 text-xs text-slate-500">Generated {new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(recommendation.generated_at))}</p>
    </section>
  );
};

export default RecommendationCard;
