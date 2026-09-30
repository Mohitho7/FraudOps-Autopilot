import React from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const Transactions = () => {
  return (
    <PageContainer 
      title="Transactions" 
      description="All monitored transactions and their preliminary risk scores."
    >
      <EmptyState 
        title="Coming in Batch 3"
        message="The transaction queue, filtering, and data table will be implemented in the next phase once the API is connected."
      />
    </PageContainer>
  );
};

export default Transactions;
