import React from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const RuleSimulation = () => {
  return (
    <PageContainer 
      title="Rule Simulation" 
      description="Test rule thresholds against historical data before deployment."
    >
      <EmptyState 
        title="Coming in Batch 5"
        message="Simulation environment will be available in the final phases."
      />
    </PageContainer>
  );
};

export default RuleSimulation;
