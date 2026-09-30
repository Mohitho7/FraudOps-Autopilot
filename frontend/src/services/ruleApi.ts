import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';
import apiClient from './apiClient';
import { mockRules, mockSimulationResult } from '../mocks/ruleMock';
import type { FraudRule, RuleSimulationInput, RuleSimulationResult } from '../types/rule';

export const ruleApi = {
  async getRules(): Promise<FraudRule[]> {
    if (isEndpointConfigured(API_ENDPOINTS.rules.list)) {
      return apiClient.get<FraudRule[]>(API_ENDPOINTS.rules.list);
    }
    await new Promise(resolve => setTimeout(resolve, 350));
    return [...mockRules];
  },

  async simulateRules(input: RuleSimulationInput): Promise<RuleSimulationResult> {
    if (isEndpointConfigured(API_ENDPOINTS.rules.simulation)) {
      return apiClient.post<RuleSimulationResult>(API_ENDPOINTS.rules.simulation, input);
    }
    await new Promise(resolve => setTimeout(resolve, 600));
    return { ...mockSimulationResult, triggered_rules: [...mockSimulationResult.triggered_rules], non_triggered_rules: [...mockSimulationResult.non_triggered_rules] };
  },
};

export default ruleApi;