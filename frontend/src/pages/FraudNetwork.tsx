import React from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const FraudNetwork = () => {
  return (
    <PageContainer 
      title="Fraud Network" 
      description="Visual relationship graph of connected entities, devices, and transactions."
    >
      <EmptyState 
        title="Coming in Batch 4"
        message="The entity relationship visualization will be integrated after core investigation logic is complete."
      />
    </PageContainer>
  );
};

export default FraudNetwork;
