import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import RiskBadge from '../components/RiskBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import RuleResultCard from '../components/RuleResultCard';
import InvestigationTimeline from '../components/InvestigationTimeline';
import EvidenceCard from '../components/EvidenceCard';
import { useTransaction } from '../hooks/useTransactions';
import { 
  ArrowLeft, 
  MapPin, 
  CreditCard, 
  Smartphone, 
  Globe, 
  Clock, 
  Building2, 
  User, 
  AlertTriangle,
  FolderOpen
} from 'lucide-react';

const TransactionDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: transaction, isLoading, isError, refetch } = useTransaction(id || '');

  if (isLoading) {
    return (
      <PageContainer title="Transaction Details">
        <LoadingState message="Loading transaction data..." />
      </PageContainer>
    );
  }

  if (isError || !transaction) {
    return (
      <PageContainer title="Transaction Details">
        <ErrorState 
          title="Transaction not found"
          message="We couldn't load the details for this transaction. It may not exist or you might not have access."
          onRetry={() => refetch()}
        />
        <div className="mt-4 flex justify-center">
          <button 
            onClick={() => navigate('/transactions')}
            className="text-primary hover:underline text-sm font-medium"
          >
            Return to Transactions Queue
          </button>
        </div>
      </PageContainer>
    );
  }

  const formatTimestamp = (timestamp: string) => {
    return new Intl.DateTimeFormat('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(new Date(timestamp));
  };

  return (
    <PageContainer 
      title={`Transaction ${transaction.id}`}
      description="Detailed investigation view for a single transaction."
      actions={
        transaction.case_id ? (
          <button
            onClick={() => navigate(`/cases/${transaction.case_id}`)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover text-sm font-medium shadow-sm transition-colors"
          >
            <FolderOpen className="w-4 h-4" />
            View Associated Case
          </button>
        ) : undefined
      }
    >
      <button 
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-800 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Main Column */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Header & Status Card */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="border-b border-gray-100 bg-gray-50/50 p-5 flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-slate-400" />
                  Transaction Summary
                </h2>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-1 rounded-md text-xs font-semibold capitalize border ${
                  transaction.status === 'flagged' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                  transaction.status === 'escalated' ? 'bg-red-50 text-red-700 border-red-200' :
                  'bg-slate-100 text-slate-700 border-slate-200'
                }`}>
                  {transaction.status.replace('_', ' ')}
                </span>
                <RiskBadge level={transaction.risk_level} />
              </div>
            </div>
            
            <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Amount</p>
                <p className="text-xl font-bold text-slate-800">₹{transaction.amount.toLocaleString('en-IN')}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Date & Time</p>
                <p className="text-sm font-medium text-slate-800">{formatTimestamp(transaction.timestamp)}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Payment Method</p>
                <p className="text-sm font-medium text-slate-800 capitalize">{transaction.payment_method?.replace('_', ' ') || 'Not available'}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Type</p>
                <p className="text-sm font-medium text-slate-800 capitalize">{transaction.transaction_type?.replace('_', ' ') || 'Not available'}</p>
              </div>
            </div>
          </div>

          {/* Risk Overview & Triggered Rules */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-slate-400" />
              Risk Overview
            </h3>
            
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 rounded-full flex items-center justify-center border-4 border-red-100 bg-red-50">
                <span className="text-xl font-bold text-red-600">{transaction.risk_score}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">Overall Risk Score</p>
                <p className="text-xs text-slate-500">Calculated deterministically by rules engine</p>
              </div>
            </div>

            <div className="space-y-3">
              {transaction.rule_results?.length ? (
                transaction.rule_results.map(rule => (
                  <RuleResultCard
                    key={rule.rule_id}
                    ruleName={rule.rule_name}
                    description={rule.reason || rule.description}
                    isTriggered={rule.triggered}
                    scoreImpact={rule.score_impact}
                  />
                ))
              ) : (
                <p className="text-sm text-slate-500 italic">No specific rule results available for this transaction.</p>
              )}
            </div>
          </div>

          {/* Context Sections */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Customer Context */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <h3 className="text-md font-semibold text-slate-800 mb-4 flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400" />
                Customer Context
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Name</span>
                  <span className="text-sm font-medium text-slate-800">{transaction.customer_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">ID</span>
                  <span className="text-sm font-mono text-slate-600">{transaction.customer_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Account Age</span>
                  <span className="text-sm text-slate-800">{transaction.customer_context?.account_age_days ? `${transaction.customer_context.account_age_days} days` : 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Typical Range</span>
                  <span className="text-sm text-slate-800">{transaction.customer_context?.typical_transaction_range || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Known Location</span>
                  <span className="text-sm text-slate-800">{transaction.customer_context?.known_location || 'Not available'}</span>
                </div>
              </div>
            </div>

            {/* Merchant Context */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <h3 className="text-md font-semibold text-slate-800 mb-4 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-slate-400" />
                Merchant Context
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Name</span>
                  <span className="text-sm font-medium text-slate-800">{transaction.merchant_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Category</span>
                  <span className="text-sm text-slate-800 capitalize">{transaction.category.replace('_', ' ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Location</span>
                  <span className="text-sm text-slate-800">{transaction.merchant_context?.location || transaction.location || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Typical Amount</span>
                  <span className="text-sm text-slate-800">{transaction.merchant_context?.typical_transaction_amount || 'Not available'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Related Activity */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5 text-slate-400" />
              Related Activity
            </h3>
            {transaction.related_activity?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-500 uppercase bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 rounded-tl-md">Entity</th>
                      <th className="px-4 py-3">Description</th>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3 rounded-tr-md">Relationship</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {transaction.related_activity.map(activity => (
                      <tr key={activity.id} className="hover:bg-gray-50/50">
                        <td className="px-4 py-3 font-mono text-slate-600">{activity.id}</td>
                        <td className="px-4 py-3 text-slate-800">{activity.description}</td>
                        <td className="px-4 py-3 text-slate-500 whitespace-nowrap">{formatTimestamp(activity.date)}</td>
                        <td className="px-4 py-3 text-slate-600">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">
                            {activity.relationship}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-500 italic">No related activity available.</p>
            )}
          </div>

        </div>

        {/* Sidebar Column */}
        <div className="space-y-6">
          
          {/* Device & Location */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider">Technical Details</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <Smartphone className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-slate-500">Device</p>
                  <p className="text-sm text-slate-800">{transaction.device_information || 'Not available'}</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Globe className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-slate-500">IP Address</p>
                  <p className="text-sm text-slate-800 font-mono">{transaction.ip_address || 'Not available'}</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <MapPin className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-slate-500">Transaction Location</p>
                  <p className="text-sm text-slate-800">{transaction.location || 'Not available'}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Evidence Pack */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider">Evidence Pack</h3>
            {transaction.evidence?.length ? (
              <div className="space-y-3">
                {transaction.evidence.map(item => (
                  <EvidenceCard
                    key={item.id}
                    title={item.source}
                    description={item.summary}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 italic">No evidence has been attached to this transaction.</p>
            )}
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider">Timeline</h3>
            {transaction.timeline?.length ? (
              <div className="mt-6">
                <InvestigationTimeline steps={transaction.timeline} />
              </div>
            ) : (
              <p className="text-sm text-slate-500 italic">Timeline not available.</p>
            )}
          </div>

        </div>

      </div>
    </PageContainer>
  );
};

export default TransactionDetail;
