import React from 'react';
import { CircleDot } from 'lucide-react';

interface TimelineStep {
  id: string;
  title: string;
  description?: string;
  timestamp?: string;
  status: 'completed' | 'current' | 'pending';
}

interface InvestigationTimelineProps {
  steps: TimelineStep[];
}

const InvestigationTimeline: React.FC<InvestigationTimelineProps> = ({ steps }) => {
  return (
    <div className="flow-root">
      <ul className="-mb-8">
        {steps.map((step, stepIdx) => (
          <li key={step.id}>
            <div className="relative pb-8">
              {stepIdx !== steps.length - 1 ? (
                <span className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
              ) : null}
              <div className="relative flex space-x-3">
                <div>
                  <span className={`h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white ${
                    step.status === 'completed' ? 'bg-primary' : 
                    step.status === 'current' ? 'bg-amber-500' : 'bg-gray-300'
                  }`}>
                    <CircleDot className="h-4 w-4 text-white" aria-hidden="true" />
                  </span>
                </div>
                <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                  <div>
                    <p className={`text-sm font-medium ${step.status === 'pending' ? 'text-gray-500' : 'text-slate-800'}`}>
                      {step.title}
                    </p>
                    {step.description && (
                      <p className="mt-1 text-sm text-slate-500">
                        {step.description}
                      </p>
                    )}
                  </div>
                  {step.timestamp && (
                    <div className="whitespace-nowrap text-right text-xs text-gray-500">
                      {step.timestamp}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default InvestigationTimeline;
