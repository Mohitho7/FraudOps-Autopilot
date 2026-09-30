import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ReviewActionPanel from './ReviewActionPanel';

describe('ReviewActionPanel', () => {
  it('requires confirmation before submitting a decision and sends notes', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ReviewActionPanel caseId="CASE-2001" onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/reviewer notes/i), 'Reviewed supporting evidence.');
    await user.click(screen.getByRole('button', { name: 'Reject' }));

    expect(screen.getByRole('dialog')).toHaveTextContent('REJECT');
    expect(onSubmit).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /confirm decision/i }));
    expect(onSubmit).toHaveBeenCalledWith('REJECT', 'Reviewed supporting evidence.');
  });

  it('can cancel confirmation without submitting', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ReviewActionPanel caseId="CASE-2001" onSubmit={onSubmit} />);

    await user.click(screen.getByRole('button', { name: 'Escalate' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
