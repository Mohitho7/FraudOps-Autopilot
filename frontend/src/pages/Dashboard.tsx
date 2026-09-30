import React from 'react';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import { ShieldAlert, AlertTriangle, CheckCircle2, TrendingUp } from 'lucide-react';
import EmptyState from '../components/EmptyState';

const Dashboard = () => {
  return (
    <PageContainer 
      title="Command Center" 
      description="Overview of current fraud operations and system alerts."
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Transactions" 
          value="--" 
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <StatCard 
          title="Flagged" 
          value="--" 
          icon={<AlertTriangle className="w-5 h-5 text-amber-500" />}
        />
        <StatCard 
          title="Critical Cases" 
          value="--" 
          icon={<ShieldAlert className="w-5 h-5 text-red-500" />}
        />
        <StatCard 
          title="Reviewed Today" 
          value="--" 
          icon={<CheckCircle2 className="w-5 h-5 text-green-500" />}
        />
      </div>

      <div className="mt-8">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">Recent Critical Cases</h3>
        <EmptyState 
          title="Coming in Batch 3"
          message="The real-time case queue and investigation dashboard will be implemented in the next phase."
        />
      </div>
    </PageContainer>
  );
};

export default Dashboard;
