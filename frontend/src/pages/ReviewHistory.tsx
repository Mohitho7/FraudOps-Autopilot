import React from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const ReviewHistory = () => {
  return (
    <PageContainer 
      title="Review History" 
      description="Audit log of all analyst decisions and actions taken."
    >
      <EmptyState 
        title="Coming in Batch 5"
        message="Review audit logs and historical analysis tools will be built in later phases."
      />
    </PageContainer>
  );
};

export default ReviewHistory;
