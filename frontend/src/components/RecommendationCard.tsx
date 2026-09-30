import React from 'react';
import { Bot } from 'lucide-react';

interface RecommendationCardProps {
  recommendation: 'REVIEW' | 'ALLOW' | 'BLOCK' | 'ESCALATE';
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  reasonSummary: string;
}

const RecommendationCard: React.FC<RecommendationCardProps> = ({ recommendation, confidence, reasonSummary }) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
      <div className="flex items-center space-x-3 mb-4">
        <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
          <Bot className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Agent Recommendation</h3>
          <p className="text-xs text-slate-500">Autonomous investigation result</p>
        </div>
      </div>
      
      <div className="flex items-baseline space-x-4 mb-4">
        <div className="text-xl font-bold text-slate-900 capitalize">
          {recommendation.toLowerCase()}
        </div>
        <div className="text-sm">
          <span className="text-slate-500">Confidence:</span>{' '}
          <span className="font-semibold text-slate-700">{confidence}</span>
        </div>
      </div>
      
      <div className="bg-gray-50 border border-gray-100 rounded p-3 text-sm text-slate-700">
        <span className="font-medium text-slate-800 mb-1 block">Reason summary:</span>
        {reasonSummary}
      </div>
    </div>
  );
};

export default RecommendationCard;
