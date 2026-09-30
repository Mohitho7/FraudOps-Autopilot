import React from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import StatCard from '../components/StatCard';
import DataTable, { Column } from '../components/DataTable';
import RiskBadge from '../components/RiskBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { 
  TrendingUp, 
  AlertTriangle, 
  ShieldAlert, 
  FolderOpen,
  CheckCircle2,
  ArrowRight
} from 'lucide-react';
import { useDashboardSummary } from '../hooks/useDashboard';
import { useTransactions } from '../hooks/useTransactions';
import type { Transaction, TransactionFilters } from '../types/transaction';

const criticalFilters: TransactionFilters = {
  search: '',
  risk_level: 'ALL',
  status: 'flagged',
  sort_by: 'risk_score',
  sort_order: 'desc',
  page: 1,
  limit: 5,
};

const Dashboard = () => {
  const navigate = useNavigate();
  const { data: summary, isLoading: summaryLoading, isError: summaryError, refetch: refetchSummary } = useDashboardSummary();
  const { data: recentCases, isLoading: casesLoading, isError: casesError, refetch: refetchCases } = useTransactions(criticalFilters);

  const columns: Column<Transaction>[] = [
    {
      key: 'id',
      header: 'Transaction ID',
      render: (item) => (
        <span className="font-mono text-sm font-medium text-slate-800">{item.id}</span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      render: (item) => (
        <span className="font-semibold text-slate-800">
          ₹{item.amount.toLocaleString('en-IN')}
        </span>
      ),
    },
    {
      key: 'customer_name',
      header: 'Customer',
      render: (item) => (
        <div>
          <p className="text-slate-800 font-medium">{item.customer_name}</p>
          <p className="text-xs text-slate-400">{item.customer_id}</p>
        </div>
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (item) => <RiskBadge level={item.risk_level} />,
    },
    {
      key: 'risk_score',
      header: 'Score',
      render: (item) => (
        <span className="font-mono text-sm font-semibold">{item.risk_score}/100</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item) => (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200 capitalize">
          {item.status.replace('_', ' ')}
        </span>
      ),
    },
    {
      key: 'action',
      header: '',
      render: (item) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/transactions/${item.id}`);
          }}
          className="text-primary hover:text-primary-hover text-sm font-medium flex items-center gap-1 transition-colors"
          aria-label={`View transaction ${item.id}`}
        >
          View <ArrowRight className="w-3 h-3" />
        </button>
      ),
    },
  ];

  // Loading state
  if (summaryLoading) {
    return (
      <PageContainer 
        title="Command Center" 
        description="Overview of current fraud operations and system alerts."
      >
        <LoadingState message="Loading command center..." />
      </PageContainer>
    );
  }

  // Error state
  if (summaryError) {
    return (
      <PageContainer 
        title="Command Center" 
        description="Overview of current fraud operations and system alerts."
      >
        <ErrorState 
          title="Failed to load dashboard"
          message="We couldn't load the command center data. Please check your connection and try again."
          onRetry={() => refetchSummary()}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer 
      title="Command Center" 
      description="Overview of current fraud operations and system alerts."
    >
      {/* Summary metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Transactions" 
          value={summary?.totalTransactions.toLocaleString('en-IN') ?? '--'} 
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <StatCard 
          title="Flagged" 
          value={summary?.flaggedTransactions.toLocaleString('en-IN') ?? '--'} 
          icon={<AlertTriangle className="w-5 h-5 text-amber-500" />}
          trend={{ value: `${summary?.highRiskTransactions ?? 0} high risk`, isPositive: false }}
        />
        <StatCard 
          title="Critical Cases" 
          value={summary?.criticalCases.toLocaleString('en-IN') ?? '--'} 
          icon={<ShieldAlert className="w-5 h-5 text-red-500" />}
        />
        <StatCard 
          title="Open Cases" 
          value={summary?.openCases.toLocaleString('en-IN') ?? '--'} 
          icon={<FolderOpen className="w-5 h-5 text-blue-500" />}
          trend={{ value: `${summary?.reviewedToday ?? 0} reviewed today`, isPositive: true }}
        />
      </div>

      {/* Flagged transactions section */}
      <div className="mt-2">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-500" />
            <h3 className="text-lg font-semibold text-slate-800">Flagged Transactions</h3>
          </div>
          <button
            onClick={() => navigate('/transactions')}
            className="flex items-center gap-1 text-sm font-medium text-primary hover:text-primary-hover transition-colors"
          >
            View All <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {casesLoading ? (
          <LoadingState message="Loading flagged transactions..." />
        ) : casesError ? (
          <ErrorState 
            title="Failed to load transactions"
            message="We couldn't load the flagged transactions."
            onRetry={() => refetchCases()}
          />
        ) : recentCases && recentCases.data.length > 0 ? (
          <DataTable
            data={recentCases.data}
            columns={columns}
            keyExtractor={(item) => item.id}
            onRowClick={(item) => navigate(`/transactions/${item.id}`)}
          />
        ) : (
          <EmptyState
            title="No flagged transactions"
            message="There are currently no transactions requiring review."
            action={
              <button
                onClick={() => navigate('/transactions')}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary hover:text-primary-hover transition-colors"
              >
                <CheckCircle2 className="w-4 h-4" />
                View all transactions
              </button>
            }
          />
        )}
      </div>
    </PageContainer>
  );
};

export default Dashboard;
