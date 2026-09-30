import React from 'react';
import { useParams } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const TransactionDetail = () => {
  const { id } = useParams<{ id: string }>();

  return (
    <PageContainer 
      title={`Transaction ${id}`} 
      description="Detailed view of transaction data and associated rule triggers."
    >
      <EmptyState 
        title="Coming in Batch 3"
        message="Detailed transaction view and context analysis will be implemented in the next phase."
      />
    </PageContainer>
  );
};

export default TransactionDetail;
