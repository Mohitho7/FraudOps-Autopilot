import React from 'react';
import { useParams } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import ReviewActionPanel from '../components/ReviewActionPanel';
import EmptyState from '../components/EmptyState';

const CaseDetail = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <PageContainer 
      title={`Case ${id}`} 
      description="Investigation results, evidence, and recommendation."
      actions={
        <div className="flex gap-2">
          {/* Action buttons placeholder for header */}
        </div>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <EmptyState 
            title="Evidence & Investigation Timeline"
            message="Agent investigation timeline and structured evidence will be rendered here in Batch 4."
          />
        </div>
        <div className="space-y-6">
          <ReviewActionPanel disabled={true} />
        </div>
      </div>
    </PageContainer>
  );
};

export default CaseDetail;
