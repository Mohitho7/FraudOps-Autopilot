import React from 'react';

type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

interface RiskBadgeProps {
  level: RiskLevel | string;
}

const RiskBadge: React.FC<RiskBadgeProps> = ({ level }) => {
  const normalizedLevel = level.toUpperCase();
  
  let styles = 'bg-gray-100 text-gray-800 border-gray-200';
  
  switch (normalizedLevel) {
    case 'CRITICAL':
      styles = 'bg-red-50 text-red-700 border-red-200';
      break;
    case 'HIGH':
      styles = 'bg-orange-50 text-orange-700 border-orange-200';
      break;
    case 'MEDIUM':
      styles = 'bg-amber-50 text-amber-700 border-amber-200';
      break;
    case 'LOW':
      styles = 'bg-green-50 text-green-700 border-green-200';
      break;
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${styles}`}>
      {normalizedLevel}
    </span>
  );
};

export default RiskBadge;
