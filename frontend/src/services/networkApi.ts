import type { FraudNetworkData } from '../types/network';
import { mockNetworkData } from '../mocks/networkMock';
import apiClient from './apiClient';
import { API_ENDPOINTS, isEndpointConfigured } from '../config/apiEndpoints';

export const networkApi = {
  async getNetwork(caseId?: string): Promise<FraudNetworkData> {
    if (isEndpointConfigured(API_ENDPOINTS.network.caseNetwork)) {
      const endpoint = API_ENDPOINTS.network.caseNetwork.replace(':caseId', caseId || '').replace('{case_id}', caseId || '');
      return apiClient.get<FraudNetworkData>(endpoint);
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
    return mockNetworkData;
  }
};
