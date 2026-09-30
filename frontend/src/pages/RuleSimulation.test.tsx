import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import RuleSimulation from './RuleSimulation';

const renderPage = () => render(<QueryClientProvider client={new QueryClient()}><RuleSimulation /></QueryClientProvider>);

describe('RuleSimulation', () => {
  it('shows structural validation without calculating a fraud result', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: 'Run simulation' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Complete all required fields.');
  });
});
