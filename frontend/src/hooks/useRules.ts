import { useMutation, useQuery } from '@tanstack/react-query';
import { ruleApi } from '../services/ruleApi';
import type { RuleSimulationInput } from '../types/rule';

export const useRules = () => useQuery({
  queryKey: ['rules'],
  queryFn: () => ruleApi.getRules(),
  staleTime: 60_000,
});

export const useRuleSimulation = () => useMutation({
  mutationFn: (input: RuleSimulationInput) => ruleApi.simulateRules(input),
});
