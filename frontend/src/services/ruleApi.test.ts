import { describe, expect, it } from 'vitest';
import { ruleApi } from './ruleApi';

describe('ruleApi mock fallback', () => {
  it('returns the mock rule catalog when the endpoint is empty', async () => {
    const rules = await ruleApi.getRules();
    expect(rules.length).toBeGreaterThan(0);
    expect(rules[0]).toHaveProperty('id');
  });

  it('returns structured simulation output without calculating in the UI', async () => {
    const result = await ruleApi.simulateRules({
      amount: 100,
      customer: 'C-1',
      merchant: 'M-1',
      location: 'Mumbai',
      transaction_count: 2,
      time_interval_minutes: 10,
      device: 'D-1',
    });
    expect(result.risk_level).toBe('HIGH');
    expect(result.triggered_rules.length).toBeGreaterThan(0);
    expect(result.non_triggered_rules.length).toBeGreaterThan(0);
  });
});
