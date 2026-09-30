import React from 'react';
import { Search } from 'lucide-react';

interface EvidenceCardProps {
  title: string;
  description: string;
  details?: React.ReactNode;
}

const EvidenceCard: React.FC<EvidenceCardProps> = ({ title, description, details }) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b border-gray-100 bg-gray-50/50 flex items-center space-x-2">
        <Search className="w-4 h-4 text-primary" />
        <h4 className="font-semibold text-slate-800 text-sm">{title}</h4>
      </div>
      <div className="p-4">
        <p className="text-sm text-slate-600 mb-3">{description}</p>
        {details && (
          <div className="bg-slate-50 rounded p-3 text-sm text-slate-700 border border-slate-100">
            {details}
          </div>
        )}
      </div>
    </div>
  );
};

export default EvidenceCard;
