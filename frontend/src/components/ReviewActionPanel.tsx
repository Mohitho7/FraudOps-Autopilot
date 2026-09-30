import React, { useEffect, useRef, useState } from 'react';
import { Check, XCircle, ShieldAlert } from 'lucide-react';
import type { DecisionAction } from '../types/review';

interface ReviewActionPanelProps {
  caseId: string;
  onSubmit: (decision: DecisionAction, notes: string) => void;
  disabled?: boolean;
  isSubmitting?: boolean;
}

const ReviewActionPanel: React.FC<ReviewActionPanelProps> = ({
  caseId,
  onSubmit,
  disabled = false,
  isSubmitting = false,
}) => {
  const [selectedDecision, setSelectedDecision] = useState<DecisionAction | null>(null);
  const [notes, setNotes] = useState('');
  const confirmButtonRef = useRef<HTMLButtonElement>(null);

  const requestConfirmation = (decision: DecisionAction) => {
    setSelectedDecision(decision);
  };

  const confirmDecision = () => {
    if (!selectedDecision) return;
    onSubmit(selectedDecision, notes.trim());
    setSelectedDecision(null);
    setNotes('');
  };

  useEffect(() => {
    if (!selectedDecision) return;
    confirmButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSelectedDecision(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedDecision]);

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Human reviewer decision</p>
        <h3 className="text-sm font-semibold text-slate-800 mt-1">Choose the final case action</h3>
      </div>
      <label htmlFor="review-notes" className="block text-xs font-medium text-slate-600 mb-2">
        Reviewer notes <span className="font-normal text-slate-400">(optional, 5,000 characters maximum)</span>
      </label>
      <textarea
        id="review-notes"
        value={notes}
        onChange={(event) => setNotes(event.target.value.slice(0, 5000))}
        disabled={disabled || isSubmitting}
        rows={3}
        placeholder="Record the evidence supporting your decision..."
        className="w-full resize-y rounded-md border border-gray-300 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:bg-gray-50"
      />
      <div className="flex flex-col sm:flex-row gap-3">
        <button 
          onClick={() => requestConfirmation('APPROVE')}
          disabled={disabled || isSubmitting}
          type="button"
          className="flex-1 flex items-center justify-center space-x-2 bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-md font-medium text-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Check className="w-4 h-4" />
          <span>Approve</span>
        </button>
        <button 
          onClick={() => requestConfirmation('REJECT')}
          disabled={disabled || isSubmitting}
          type="button"
          className="flex-1 flex items-center justify-center space-x-2 bg-red-600 border border-transparent text-white px-4 py-2 rounded-md font-medium text-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <XCircle className="w-4 h-4" />
          <span>Reject</span>
        </button>
        <button 
          onClick={() => requestConfirmation('ESCALATE')}
          disabled={disabled || isSubmitting}
          type="button"
          className="flex-1 flex items-center justify-center space-x-2 bg-amber-500 border border-transparent text-white px-4 py-2 rounded-md font-medium text-sm hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Escalate</span>
        </button>
      </div>
      {isSubmitting && <p className="text-xs text-center text-slate-500 mt-3">Submitting decision...</p>}

      {selectedDecision && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="presentation">
          <div role="dialog" aria-modal="true" aria-labelledby="confirm-review-title" className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h4 id="confirm-review-title" className="text-lg font-semibold text-slate-900">Confirm review decision</h4>
            <p className="mt-3 text-sm text-slate-600">Submit <strong>{selectedDecision}</strong> for case <strong>{caseId}</strong>?</p>
            <p className="mt-2 text-xs text-slate-500">This records the human reviewer outcome and updates the case.</p>
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => setSelectedDecision(null)} className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-gray-50">Cancel</button>
              <button ref={confirmButtonRef} type="button" onClick={confirmDecision} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover">Confirm decision</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReviewActionPanel;
