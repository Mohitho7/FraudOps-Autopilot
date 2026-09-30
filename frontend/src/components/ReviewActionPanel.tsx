import React from 'react';
import { Check, XCircle, ShieldAlert } from 'lucide-react';

interface ReviewActionPanelProps {
  onClear?: () => void;
  onConfirm?: () => void;
  onEscalate?: () => void;
  disabled?: boolean;
}

const ReviewActionPanel: React.FC<ReviewActionPanelProps> = ({ disabled = true }) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
      <h3 className="text-sm font-semibold text-slate-800 mb-4">Review Actions</h3>
      <div className="flex flex-col sm:flex-row gap-3">
        <button 
          disabled={disabled}
          className="flex-1 flex items-center justify-center space-x-2 bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-md font-medium text-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Check className="w-4 h-4" />
          <span>Clear</span>
        </button>
        <button 
          disabled={disabled}
          className="flex-1 flex items-center justify-center space-x-2 bg-red-600 border border-transparent text-white px-4 py-2 rounded-md font-medium text-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <XCircle className="w-4 h-4" />
          <span>Confirm Fraud</span>
        </button>
        <button 
          disabled={disabled}
          className="flex-1 flex items-center justify-center space-x-2 bg-amber-500 border border-transparent text-white px-4 py-2 rounded-md font-medium text-sm hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Escalate</span>
        </button>
      </div>
      {disabled && (
        <p className="text-xs text-center text-slate-500 mt-3">
          Actions are disabled in Batch 2 preview.
        </p>
      )}
    </div>
  );
};

export default ReviewActionPanel;
