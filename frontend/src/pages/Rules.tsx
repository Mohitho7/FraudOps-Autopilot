import React from 'react';
import PageContainer from '../components/PageContainer';
import DataTable from '../components/DataTable';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import RiskBadge from '../components/RiskBadge';
import { useRules } from '../hooks/useRules';

const Rules = () => {
  const rules = useRules();
  return (
    <PageContainer 
      title="Rules Management" 
      description="Configure and monitor deterministic fraud detection rules."
    >
      {rules.isLoading && <LoadingState message="Loading rule catalog..." />}
      {rules.isError && <ErrorState title="Rules unavailable" message="The rule catalog could not be loaded." onRetry={() => rules.refetch()} />}
      {rules.data && rules.data.length === 0 && <EmptyState title="No rules available" message="The backend returned an empty rule catalog." />}
      {rules.data && rules.data.length > 0 && <DataTable data={rules.data} keyExtractor={rule => rule.id} columns={[
        { key: 'id', header: 'Rule ID' },
        { key: 'name', header: 'Rule name', render: rule => <span className="font-medium text-slate-800">{rule.name}</span> },
        { key: 'description', header: 'Description', render: rule => <span className="whitespace-normal">{rule.description}</span> },
        { key: 'category', header: 'Category' },
        { key: 'severity', header: 'Severity', render: rule => <RiskBadge level={rule.severity} /> },
        { key: 'status', header: 'Status', render: rule => <span className={rule.status === 'ACTIVE' ? 'text-green-700' : 'text-slate-500'}>{rule.status}</span> },
        { key: 'updated_at', header: 'Last updated', render: rule => new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(new Date(rule.updated_at)) },
      ]} />}
    </PageContainer>
  );
};

export default Rules;
