import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import LoadingState from '../components/LoadingState';
import { useNetwork } from '../hooks/useNetwork';
import type { NodeType } from '../types/network';

const FraudNetwork = () => {
  const network = useNetwork();
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const typeLabels: NodeType[] = ['Customer', 'Transaction', 'Merchant', 'Device', 'Location'];
  const selected = network.data?.nodes.find(node => node.id === selectedNode);
  const connected = network.data?.edges.filter(edge => edge.source === selectedNode || edge.target === selectedNode) || [];

  return (
    <PageContainer 
      title="Fraud Network" 
      description="Visual relationship graph of connected entities, devices, and transactions."
    >
      {network.isLoading && <LoadingState message="Loading related entities..." />}
      {network.isError && <ErrorState title="Network unavailable" message="We couldn't load related entities for this investigation." onRetry={() => network.refetch()} />}
      {network.data && network.data.nodes.length === 0 && <EmptyState title="No related network activity found" message="No connected entities were returned for this case." />}
      {network.data && network.data.nodes.length > 0 && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-3" aria-label="Network legend">
            {typeLabels.map(type => <span key={type} className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-slate-700">{type}</span>)}
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <section className="rounded-lg border border-gray-200 bg-white p-5" aria-labelledby="network-map-title">
              <h2 id="network-map-title" className="text-sm font-semibold text-slate-800">Relationship map</h2>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {network.data.nodes.map(node => {
                  const isConnected = !selectedNode || node.id === selectedNode || connected.some(edge => edge.source === node.id || edge.target === node.id);
                  return <button type="button" key={node.id} onClick={() => setSelectedNode(node.id === selectedNode ? null : node.id)} aria-pressed={node.id === selectedNode} className={`rounded-md border p-3 text-left transition-colors ${node.id === selectedNode ? 'border-primary bg-sky-50' : 'border-gray-200 bg-gray-50'} ${isConnected ? 'opacity-100' : 'opacity-35'}`}><span className="block text-xs font-semibold uppercase tracking-wider text-slate-500">{node.type}</span><span className="mt-1 block font-medium text-slate-800">{node.label}</span><span className="mt-1 block font-mono text-xs text-slate-500">{node.id}</span></button>;
                })}
              </div>
              {selected && <p className="mt-4 rounded bg-slate-50 p-3 text-sm text-slate-600"><strong>{selected.label}</strong>: {selected.details || 'No additional details provided.'}</p>}
            </section>
            <section className="rounded-lg border border-gray-200 bg-white p-5" aria-labelledby="relationship-list-title">
              <h2 id="relationship-list-title" className="text-sm font-semibold text-slate-800">Related entities</h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm"><thead className="border-b border-gray-200 text-xs uppercase text-slate-500"><tr><th className="px-2 py-2">Entity</th><th className="px-2 py-2">Relationship</th><th className="px-2 py-2">Connected to</th></tr></thead><tbody className="divide-y divide-gray-100">{network.data.edges.map(edge => { const source = network.data.nodes.find(node => node.id === edge.source); const target = network.data.nodes.find(node => node.id === edge.target); return <tr key={edge.id}><td className="px-2 py-2 font-mono text-xs">{source?.id}</td><td className="px-2 py-2 text-slate-600">{edge.label}</td><td className="px-2 py-2 font-mono text-xs">{target?.id}</td></tr>; })}</tbody></table>
              </div>
            </section>
          </div>
        </div>
      )}
    </PageContainer>
  );
};

export default FraudNetwork;
