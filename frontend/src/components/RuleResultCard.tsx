import React from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

interface RuleResultCardProps {
  ruleName: string;
  description: string;
  isTriggered: boolean;
  scoreImpact?: number;
}

const RuleResultCard: React.FC<RuleResultCardProps> = ({ ruleName, description, isTriggered, scoreImpact }) => {
  return (
    <div className={`p-4 rounded-lg border flex items-start space-x-3 transition-colors ${isTriggered ? 'bg-red-50/50 border-red-100' : 'bg-white border-gray-200'}`}>
      <div className="mt-0.5 shrink-0">
        {isTriggered ? (
          <AlertCircle className="w-5 h-5 text-red-500" />
        ) : (
          <CheckCircle2 className="w-5 h-5 text-green-500" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-start">
          <h4 className="text-sm font-semibold text-slate-800">{ruleName}</h4>
          {scoreImpact && isTriggered && (
            <span className="text-xs font-bold text-red-700 bg-red-100 px-2 py-0.5 rounded ml-2 shrink-0">
              +{scoreImpact} risk
            </span>
          )}
        </div>
        <p className="text-sm text-slate-600 mt-1">{description}</p>
        <p className="text-xs font-medium mt-2">
          Status: <span className={isTriggered ? 'text-red-600' : 'text-green-600'}>{isTriggered ? 'Triggered' : 'Passed'}</span>
        </p>
      </div>
    </div>
  );
};

export default RuleResultCard;
