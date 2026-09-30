import React from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const Rules = () => {
  return (
    <PageContainer 
      title="Rules Management" 
      description="Configure and monitor deterministic fraud detection rules."
    >
      <EmptyState 
        title="Coming in Batch 5"
        message="Rule management interface will be added in a later phase."
      />
    </PageContainer>
  );
};

export default Rules;
