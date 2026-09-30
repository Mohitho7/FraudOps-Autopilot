import React from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';

const Cases = () => {
  return (
    <PageContainer 
      title="Investigation Cases" 
      description="Queue of flagged activities requiring autonomous or human investigation."
    >
      <EmptyState 
        title="Coming in Batch 3"
        message="The case queue and filtering system will be built out in the next phase."
      />
    </PageContainer>
  );
};

export default Cases;
