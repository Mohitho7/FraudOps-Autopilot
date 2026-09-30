import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';

describe('App', () => {
  it('opens the dashboard directly at root without login', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><App /></QueryClientProvider>);
    expect(document.body).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Command Center', level: 2 })).toBeInTheDocument();
  });
});
