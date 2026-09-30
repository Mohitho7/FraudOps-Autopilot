import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import RuleResultCard from '../components/RuleResultCard';
import { useRuleSimulation } from '../hooks/useRules';
import type { RuleSimulationInput } from '../types/rule';

const RuleSimulation = () => {
  const simulate = useRuleSimulation();
  const [form, setForm] = useState<RuleSimulationInput>({ amount: 0, customer: '', merchant: '', location: '', transaction_count: 1, time_interval_minutes: 1, device: '' });
  const [validationError, setValidationError] = useState('');
  const update = (key: keyof RuleSimulationInput, value: string) => setForm(current => ({ ...current, [key]: ['amount', 'transaction_count', 'time_interval_minutes'].includes(key) ? Number(value) : value }));
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.customer.trim() || !form.merchant.trim() || !form.location.trim() || !form.device.trim()) return setValidationError('Complete all required fields.');
    if (!Number.isFinite(form.amount) || form.amount < 0) return setValidationError('Amount must be zero or greater.');
    if (!Number.isInteger(form.transaction_count) || form.transaction_count < 1) return setValidationError('Transaction count must be a positive whole number.');
    if (!Number.isFinite(form.time_interval_minutes) || form.time_interval_minutes <= 0) return setValidationError('Time interval must be greater than zero.');
    setValidationError('');
    simulate.mutate(form);
  };
  return (
    <PageContainer 
      title="Rule Simulation" 
      description="Test rule thresholds against historical data before deployment."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <form onSubmit={submit} className="rounded-lg border border-gray-200 bg-white p-5 lg:col-span-1">
          <h2 className="text-sm font-semibold text-slate-800">Simulation input</h2>
          <p className="mt-1 text-xs text-slate-500">Inputs are sent to the rule simulation service. This page does not calculate risk.</p>
          <div className="mt-4 space-y-3">
            {([['amount', 'Transaction amount', 'number'], ['customer', 'Customer', 'text'], ['merchant', 'Merchant', 'text'], ['location', 'Location', 'text'], ['transaction_count', 'Transaction count', 'number'], ['time_interval_minutes', 'Time interval (minutes)', 'number'], ['device', 'Device', 'text']] as const).map(([key, label, type]) => <label key={key} className="block text-sm text-slate-700">{label}{key !== 'amount' && <span className="text-slate-400"> (required)</span>}<input type={type} value={form[key]} onChange={event => update(key, event.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2" /></label>)}
          </div>
          {validationError && <p role="alert" className="mt-3 text-sm text-red-600">{validationError}</p>}
          <button type="submit" disabled={simulate.isPending} className="mt-5 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50">{simulate.isPending ? 'Running simulation...' : 'Run simulation'}</button>
        </form>
        <section className="lg:col-span-2">
          {simulate.isPending && <LoadingState message="Running rule simulation..." />}
          {simulate.isError && <ErrorState title="Simulation unavailable" message="The rule simulation could not be completed." onRetry={() => simulate.reset()} />}
          {!simulate.data && !simulate.isPending && !simulate.isError && <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center text-sm text-slate-500">Run a simulation to view returned rule results.</div>}
          {simulate.data && <div className="space-y-5"><div className="rounded-lg border border-gray-200 bg-white p-5"><h2 className="text-lg font-semibold text-slate-800">Simulation result</h2><div className="mt-4 flex gap-6"><div><p className="text-xs uppercase text-slate-500">Risk level</p><p className="mt-1 text-xl font-bold">{simulate.data.risk_level || 'Not provided'}</p></div><div><p className="text-xs uppercase text-slate-500">Risk score</p><p className="mt-1 text-xl font-bold">{simulate.data.risk_score ?? 'Not provided'}</p></div></div></div><div className="rounded-lg border border-gray-200 bg-white p-5"><h3 className="text-sm font-semibold text-slate-800">Triggered rules</h3><div className="mt-3 space-y-3">{simulate.data.triggered_rules.map(rule => <RuleResultCard key={rule.rule_id} ruleName={rule.rule_name} description={rule.reason || rule.description} isTriggered={rule.triggered} scoreImpact={rule.score_impact} />)}</div><h3 className="mt-5 text-sm font-semibold text-slate-800">Not triggered</h3><div className="mt-3 space-y-3">{simulate.data.non_triggered_rules.map(rule => <RuleResultCard key={rule.rule_id} ruleName={rule.rule_name} description={rule.reason || rule.description} isTriggered={rule.triggered} scoreImpact={rule.score_impact} />)}</div></div></div>}
        </section>
      </div>
    </PageContainer>
  );
};

export default RuleSimulation;
