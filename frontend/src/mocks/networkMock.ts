import type { FraudNetworkData } from '../types/network';

export const mockNetworkData: FraudNetworkData = {
  nodes: [
    { id: 'C-1028', type: 'Customer', label: 'Rajesh Kumar' },
    { id: 'TXN-10482', type: 'Transaction', label: '₹8,500,000', is_focus: true },
    { id: 'TXN-10481', type: 'Transaction', label: '₹4,100,000' },
    { id: 'M-FUEL-019', type: 'Merchant', label: 'PetroMax Fuels' },
    { id: 'DEV-IP-103', type: 'Device', label: 'iPhone 13 (London IP)' },
    { id: 'LOC-MUM', type: 'Location', label: 'Mumbai, MH' },
    { id: 'LOC-LON', type: 'Location', label: 'London, UK' }
  ],
  edges: [
    { id: 'e1', source: 'C-1028', target: 'TXN-10482', label: 'Initiated' },
    { id: 'e2', source: 'C-1028', target: 'TXN-10481', label: 'Initiated' },
    { id: 'e3', source: 'TXN-10482', target: 'M-FUEL-019', label: 'Paid to' },
    { id: 'e4', source: 'C-1028', target: 'DEV-IP-103', label: 'Used device' },
    { id: 'e5', source: 'TXN-10482', target: 'DEV-IP-103', label: 'Origin' },
    { id: 'e6', source: 'DEV-IP-103', target: 'LOC-LON', label: 'Located in' },
    { id: 'e7', source: 'M-FUEL-019', target: 'LOC-MUM', label: 'Located in' },
  ]
};
