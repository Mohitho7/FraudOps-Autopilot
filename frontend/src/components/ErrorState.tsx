import React from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

const ErrorState: React.FC<ErrorStateProps> = ({ 
  title = 'An error occurred', 
  message = 'We encountered a problem while trying to load this data.', 
  onRetry 
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white border border-red-100 rounded-lg shadow-sm">
      <div className="w-12 h-12 bg-red-50 text-red-500 rounded-full flex items-center justify-center mb-4">
        <AlertOctagon className="w-6 h-6" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 mb-6 max-w-md">{message}</p>
      
      {onRetry && (
        <button 
          onClick={onRetry}
          className="flex items-center space-x-2 px-4 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-slate-700 hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Try again</span>
        </button>
      )}
    </div>
  );
};

export default ErrorState;
