export const API_ENDPOINTS = {
  auth: {
    login: '',
    logout: '',
  },
  dashboard: {
    stats: '',
  },
  transactions: {
    list: '',
    detail: '',
  },
  cases: {
    list: '',
    detail: '',
  },
  review: {
    recommendation: '',
    decision: '',
    history: '',
  },
  network: {
    caseNetwork: '',
  },
  rules: {
    list: '',
    simulation: '',
  },
} as const;

export const isEndpointConfigured = (endpoint: string): boolean => endpoint.trim().length > 0;

export const isAnyEndpointConfigured = (): boolean => Object.values(API_ENDPOINTS).some(group => Object.values(group).some(isEndpointConfigured));
