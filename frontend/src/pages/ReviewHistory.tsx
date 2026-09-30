import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import DataTable from '../components/DataTable';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import RiskBadge from '../components/RiskBadge';
import { useReviewHistory } from '../hooks/useReview';
import type { DecisionAction, ReviewFilters } from '../types/review';
import type { RiskLevel } from '../types/transaction';

const ReviewHistory = () => {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ReviewFilters>({
    search: '', decision: 'ALL', risk_level: 'ALL', sort_by: 'timestamp', sort_order: 'desc', page: 1, limit: 10,
  });
  const history = useReviewHistory(filters);
  const updateFilter = <K extends keyof ReviewFilters>(key: K, value: ReviewFilters[K]) => {
    setFilters(current => ({ ...current, [key]: value, page: 1 }));
  };

  return (
    <PageContainer 
      title="Review History" 
      description="Audit log of all analyst decisions and actions taken."
    >
      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-4">
        <input aria-label="Search case or transaction" value={filters.search} onChange={event => updateFilter('search', event.target.value)} placeholder="Search case or transaction" className="rounded-md border border-gray-300 px-3 py-2 text-sm" />
        <select aria-label="Filter by decision" value={filters.decision} onChange={event => updateFilter('decision', event.target.value as DecisionAction | 'ALL')} className="rounded-md border border-gray-300 px-3 py-2 text-sm">
          <option value="ALL">All decisions</option><option value="APPROVE">Approve</option><option value="REJECT">Reject</option><option value="ESCALATE">Escalate</option>
        </select>
        <select aria-label="Filter by risk level" value={filters.risk_level} onChange={event => updateFilter('risk_level', event.target.value as RiskLevel | 'ALL')} className="rounded-md border border-gray-300 px-3 py-2 text-sm">
          <option value="ALL">All risk levels</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option>
        </select>
        <select aria-label="Sort review history" value={`${filters.sort_by}-${filters.sort_order}`} onChange={event => { const [sort_by, sort_order] = event.target.value.split('-') as [ReviewFilters['sort_by'], ReviewFilters['sort_order']]; setFilters(current => ({ ...current, sort_by, sort_order, page: 1 })); }} className="rounded-md border border-gray-300 px-3 py-2 text-sm">
          <option value="timestamp-desc">Newest first</option><option value="timestamp-asc">Oldest first</option><option value="risk_score-desc">Highest risk first</option><option value="risk_score-asc">Lowest risk first</option>
        </select>
      </div>
      {history.isLoading && <LoadingState message="Loading review history..." />}
      {history.isError && <ErrorState title="Review history unavailable" message="We couldn't load completed reviews right now." onRetry={() => history.refetch()} />}
      {history.data && history.data.data.length === 0 && <EmptyState title="No review history found" message="No completed reviews match the current filters." />}
      {history.data && history.data.data.length > 0 && (
        <>
          <DataTable
            data={history.data.data}
            keyExtractor={review => review.id}
            onRowClick={review => navigate(`/cases/${review.case_id}`)}
            columns={[
              { key: 'case_id', header: 'Case ID' },
              { key: 'transaction_id', header: 'Transaction ID' },
              { key: 'reviewer_name', header: 'Reviewer' },
              { key: 'decision', header: 'Decision', render: review => <span className="font-semibold">{review.decision}</span> },
              { key: 'risk_level', header: 'Risk', render: review => <RiskBadge level={review.risk_level} /> },
              { key: 'risk_score', header: 'Score' },
              { key: 'timestamp', header: 'Reviewed', render: review => new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(review.timestamp)) },
            ]}
          />
          <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
            <span>{history.data.total} completed review{history.data.total === 1 ? '' : 's'}</span>
            <div className="flex gap-2">
              <button type="button" disabled={filters.page <= 1} onClick={() => setFilters(current => ({ ...current, page: current.page - 1 }))} className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40">Previous</button>
              <span className="px-2 py-1">Page {history.data.page} of {Math.max(history.data.totalPages, 1)}</span>
              <button type="button" disabled={filters.page >= history.data.totalPages} onClick={() => setFilters(current => ({ ...current, page: current.page + 1 }))} className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40">Next</button>
            </div>
          </div>
        </>
      )}
    </PageContainer>
  );
};

export default ReviewHistory;
