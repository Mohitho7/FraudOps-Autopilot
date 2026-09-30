import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import DataTable, { Column } from '../components/DataTable';
import RiskBadge from '../components/RiskBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { 
  Search, 
  ArrowRight, 
  ArrowUpDown, 
  Filter, 
  X,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useTransactions } from '../hooks/useTransactions';
import type { Transaction, TransactionFilters, RiskLevel, TransactionStatus } from '../types/transaction';

const DEFAULT_FILTERS: TransactionFilters = {
  search: '',
  risk_level: 'ALL',
  status: 'ALL',
  sort_by: 'timestamp',
  sort_order: 'desc',
  page: 1,
  limit: 10,
};

const RISK_OPTIONS: { label: string; value: RiskLevel | 'ALL' }[] = [
  { label: 'All Risk Levels', value: 'ALL' },
  { label: 'Critical', value: 'CRITICAL' },
  { label: 'High', value: 'HIGH' },
  { label: 'Medium', value: 'MEDIUM' },
  { label: 'Low', value: 'LOW' },
];

const STATUS_OPTIONS: { label: string; value: TransactionStatus | 'ALL' }[] = [
  { label: 'All Statuses', value: 'ALL' },
  { label: 'Flagged', value: 'flagged' },
  { label: 'Under Review', value: 'under_review' },
  { label: 'Escalated', value: 'escalated' },
  { label: 'Cleared', value: 'cleared' },
  { label: 'Confirmed Fraud', value: 'confirmed_fraud' },
  { label: 'Pending', value: 'pending' },
];

const SORT_OPTIONS: { label: string; value: TransactionFilters['sort_by'] }[] = [
  { label: 'Timestamp', value: 'timestamp' },
  { label: 'Amount', value: 'amount' },
  { label: 'Risk Score', value: 'risk_score' },
];

const Transactions = () => {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<TransactionFilters>(DEFAULT_FILTERS);
  const [searchInput, setSearchInput] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const { data, isLoading, isError, refetch } = useTransactions(filters);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.risk_level !== 'ALL') count++;
    if (filters.status !== 'ALL') count++;
    if (filters.search) count++;
    return count;
  }, [filters]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setFilters((prev) => ({ ...prev, search: searchInput, page: 1 }));
  };

  const handleClearSearch = () => {
    setSearchInput('');
    setFilters((prev) => ({ ...prev, search: '', page: 1 }));
  };

  const handleFilterChange = (key: keyof TransactionFilters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  };

  const handleSort = (field: TransactionFilters['sort_by']) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: field,
      sort_order: prev.sort_by === field && prev.sort_order === 'desc' ? 'asc' : 'desc',
      page: 1,
    }));
  };

  const handleClearFilters = () => {
    setSearchInput('');
    setFilters(DEFAULT_FILTERS);
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return new Intl.DateTimeFormat('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }).format(date);
  };

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
      key: 'merchant_name',
      header: 'Merchant',
      render: (item) => (
        <div>
          <p className="text-slate-800">{item.merchant_name}</p>
          <p className="text-xs text-slate-400 capitalize">{item.category?.replace('_', ' ')}</p>
        </div>
      ),
    },
    {
      key: 'timestamp',
      header: 'Time',
      render: (item) => (
        <span className="text-sm text-slate-600">{formatTimestamp(item.timestamp)}</span>
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (item) => (
        <div className="flex items-center gap-2">
          <RiskBadge level={item.risk_level} />
          <span className="font-mono text-xs text-slate-400">{item.risk_score}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item) => {
        const statusStyles: Record<string, string> = {
          flagged: 'bg-amber-50 text-amber-700 border-amber-200',
          under_review: 'bg-blue-50 text-blue-700 border-blue-200',
          escalated: 'bg-red-50 text-red-700 border-red-200',
          cleared: 'bg-green-50 text-green-700 border-green-200',
          confirmed_fraud: 'bg-red-50 text-red-800 border-red-300',
          pending: 'bg-gray-50 text-gray-600 border-gray-200',
        };
        return (
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border capitalize ${statusStyles[item.status] || statusStyles.pending}`}>
            {item.status.replace('_', ' ')}
          </span>
        );
      },
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

  return (
    <PageContainer 
      title="Transactions" 
      description="Flagged and monitored transactions requiring attention."
    >
      {/* Search and filter bar */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              id="transaction-search"
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search transactions by ID, customer, or merchant..."
              className="w-full pl-10 pr-10 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-shadow"
              aria-label="Search transactions"
            />
            {searchInput && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </form>

          {/* Filter toggle */}
          <button
            id="toggle-filters"
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2.5 border rounded-lg text-sm font-medium transition-colors ${
              showFilters || activeFilterCount > 0
                ? 'bg-primary/5 border-primary/20 text-primary'
                : 'bg-white border-gray-200 text-slate-600 hover:bg-gray-50'
            }`}
            aria-label="Toggle filters"
            aria-expanded={showFilters}
          >
            <Filter className="w-4 h-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="w-5 h-5 rounded-full bg-primary text-white text-xs flex items-center justify-center">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>

        {/* Filter panel */}
        {showFilters && (
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="flex flex-col sm:flex-row gap-4 items-end">
              {/* Risk filter */}
              <div className="flex-1 min-w-[160px]">
                <label htmlFor="filter-risk" className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1.5">
                  Risk Level
                </label>
                <select
                  id="filter-risk"
                  value={filters.risk_level}
                  onChange={(e) => handleFilterChange('risk_level', e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  aria-label="Filter by risk level"
                >
                  {RISK_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Status filter */}
              <div className="flex-1 min-w-[160px]">
                <label htmlFor="filter-status" className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1.5">
                  Status
                </label>
                <select
                  id="filter-status"
                  value={filters.status}
                  onChange={(e) => handleFilterChange('status', e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  aria-label="Filter by status"
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Sort */}
              <div className="flex-1 min-w-[160px]">
                <label htmlFor="filter-sort" className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1.5">
                  Sort By
                </label>
                <div className="flex gap-1">
                  <select
                    id="filter-sort"
                    value={filters.sort_by}
                    onChange={(e) => handleSort(e.target.value as TransactionFilters['sort_by'])}
                    className="flex-1 px-3 py-2 bg-white border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    aria-label="Sort by field"
                  >
                    {SORT_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <button
                    onClick={() =>
                      setFilters((prev) => ({
                        ...prev,
                        sort_order: prev.sort_order === 'desc' ? 'asc' : 'desc',
                      }))
                    }
                    className="px-2 py-2 border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
                    aria-label={`Sort order: ${filters.sort_order === 'desc' ? 'descending' : 'ascending'}`}
                    title={filters.sort_order === 'desc' ? 'Descending' : 'Ascending'}
                  >
                    <ArrowUpDown className={`w-4 h-4 text-slate-500 transition-transform ${filters.sort_order === 'asc' ? 'rotate-180' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Clear filters */}
              {activeFilterCount > 0 && (
                <button
                  onClick={handleClearFilters}
                  className="px-3 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap"
                >
                  Clear all
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Results info */}
      {data && !isLoading && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <p>
            Showing {data.data.length} of {data.total} transaction{data.total !== 1 ? 's' : ''}
            {filters.search && <span> matching "<strong className="text-slate-700">{filters.search}</strong>"</span>}
          </p>
        </div>
      )}

      {/* Table content */}
      {isLoading ? (
        <LoadingState message="Loading transactions..." />
      ) : isError ? (
        <ErrorState
          title="Failed to load transactions"
          message="We couldn't load the transaction data. Please check your connection and try again."
          onRetry={() => refetch()}
        />
      ) : data && data.data.length > 0 ? (
        <>
          <DataTable
            data={data.data}
            columns={columns}
            keyExtractor={(item) => item.id}
            onRowClick={(item) => navigate(`/transactions/${item.id}`)}
          />

          {/* Pagination */}
          {data.totalPages > 1 && (
            <div className="flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-3">
              <p className="text-sm text-slate-500">
                Page {data.page} of {data.totalPages}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setFilters((prev) => ({ ...prev, page: prev.page - 1 }))}
                  disabled={data.page <= 1}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" /> Previous
                </button>
                <button
                  onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
                  disabled={data.page >= data.totalPages}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="Next page"
                >
                  Next <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <EmptyState
          title={filters.search || filters.risk_level !== 'ALL' || filters.status !== 'ALL'
            ? 'No matching transactions'
            : 'No flagged transactions'
          }
          message={filters.search || filters.risk_level !== 'ALL' || filters.status !== 'ALL'
            ? 'Try changing your search or filters.'
            : 'There are currently no transactions requiring review.'
          }
          action={
            activeFilterCount > 0 ? (
              <button
                onClick={handleClearFilters}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary hover:text-primary-hover transition-colors"
              >
                Clear filters
              </button>
            ) : undefined
          }
        />
      )}
    </PageContainer>
  );
};

export default Transactions;
