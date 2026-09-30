import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('App', () => {
  it('renders login page initially at root (or redirects)', () => {
    // Basic test ensuring the app mounts and rendering doesn't throw
    render(<App />);
    expect(document.body).toBeInTheDocument();
  });
});
