export type NodeType = 'Customer' | 'Transaction' | 'Merchant' | 'Device' | 'Location';

export interface NetworkNode {
  id: string;
  type: NodeType;
  label: string;
  details?: string;
  is_focus?: boolean; // Highlight the main entity being investigated
}

export interface NetworkEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

export interface FraudNetworkData {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}
