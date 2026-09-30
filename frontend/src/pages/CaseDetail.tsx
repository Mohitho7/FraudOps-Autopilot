import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PageContainer from '../components/PageContainer';
import ReviewActionPanel from '../components/ReviewActionPanel';
import RiskBadge from '../components/RiskBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import RuleResultCard from '../components/RuleResultCard';
import InvestigationTimeline from '../components/InvestigationTimeline';
import EvidenceCard from '../components/EvidenceCard';
import RecommendationCard from '../components/RecommendationCard';
import { useCase } from '../hooks/useCases';
import { useRecommendation, useSubmitDecision } from '../hooks/useReview';
import type { DecisionAction } from '../types/review';
import { getUserFacingApiMessage } from '../types/api';
import { 
  ArrowLeft,
  AlertTriangle,
  User,
  Building2,
  Clock,
  FolderOpen,
  CreditCard,
  FileText
} from 'lucide-react';

const CaseDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: caseData, isLoading, isError, refetch } = useCase(id || '');
  const recommendationQuery = useRecommendation(id || '');
  const submitDecision = useSubmitDecision();

  if (isLoading) {
    return (
      <PageContainer title="Case Details">
        <LoadingState message="Loading case details..." />
      </PageContainer>
    );
  }

  if (isError || !caseData) {
    return (
      <PageContainer title="Case Details">
        <ErrorState 
          title="Case not found"
          message="We couldn't load the details for this case. It may not exist or you might not have access."
          onRetry={() => refetch()}
        />
        <div className="mt-4 flex justify-center">
          <button 
            onClick={() => navigate('/cases')}
            className="text-primary hover:underline text-sm font-medium"
          >
            Return to Case Queue
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

  const handleDecision = (decision: DecisionAction, notes: string) => {
    submitDecision.mutate({ case_id: caseData.id, decision, notes });
  };

  return (
    <PageContainer 
      title={`Case ${caseData.id}`}
      description="Investigation workspace for the selected fraud case."
    >
      <button 
        onClick={() => navigate('/cases')}
        className="flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-800 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Cases
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Main Investigation Column */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Header & Status Card */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="border-b border-gray-100 bg-gray-50/50 p-5 flex flex-col md:flex-row md:justify-between md:items-center gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                  <FolderOpen className="w-5 h-5 text-slate-400" />
                  Case Summary
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  Opened {formatTimestamp(caseData.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-1 rounded-md text-xs font-semibold capitalize border ${
                  caseData.status === 'review_required' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                  caseData.status === 'investigating' ? 'bg-purple-50 text-purple-700 border-purple-200' :
                  caseData.status === 'open' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                  'bg-slate-100 text-slate-700 border-slate-200'
                }`}>
                  {caseData.status.replace('_', ' ')}
                </span>
                <RiskBadge level={caseData.risk_level} />
              </div>
            </div>
            
            <div className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-sm font-medium text-slate-500 mb-1 uppercase tracking-wider">Associated Transaction</h3>
                  <button 
                    onClick={() => navigate(`/transactions/${caseData.transaction_id}`)}
                    className="text-primary hover:text-primary-hover font-mono text-lg font-semibold flex items-center gap-2 group transition-colors"
                  >
                    <CreditCard className="w-5 h-5" />
                    {caseData.transaction_id}
                  </button>
                </div>
                <div className="text-right">
                  <h3 className="text-sm font-medium text-slate-500 mb-1 uppercase tracking-wider">Amount</h3>
                  <p className="text-2xl font-bold text-slate-800">₹{caseData.amount.toLocaleString('en-IN')}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Overview & Triggered Rules */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-slate-400" />
              Risk Summary
            </h3>
            
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 rounded-full flex items-center justify-center border-4 border-red-100 bg-red-50 shrink-0">
                <span className="text-xl font-bold text-red-600">{caseData.risk_score}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">Overall Risk Score</p>
                <p className="text-xs text-slate-500">Determined by backend rules engine.</p>
              </div>
            </div>

            <h4 className="text-sm font-semibold text-slate-800 mb-3 uppercase tracking-wider">Triggered Rules</h4>
            <div className="space-y-3">
              {caseData.rule_results?.length ? (
                caseData.rule_results.map(rule => (
                  <RuleResultCard
                    key={rule.rule_id}
                    ruleName={rule.rule_name}
                    description={rule.reason || rule.description}
                    isTriggered={rule.triggered}
                    scoreImpact={rule.score_impact}
                  />
                ))
              ) : (
                <p className="text-sm text-slate-500 italic">No specific rule results available.</p>
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
                  <span className="text-sm font-medium text-slate-800">{caseData.customer_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">ID</span>
                  <span className="text-sm font-mono text-slate-600">{caseData.customer_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Account Age</span>
                  <span className="text-sm text-slate-800">{caseData.customer_context?.account_age_days ? `${caseData.customer_context.account_age_days} days` : 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Typical Range</span>
                  <span className="text-sm text-slate-800">{caseData.customer_context?.typical_transaction_range || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">30d Txn Count</span>
                  <span className="text-sm text-slate-800">{caseData.customer_context?.recent_transaction_count_30d || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Known Location</span>
                  <span className="text-sm text-slate-800">{caseData.customer_context?.known_location || 'Not available'}</span>
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
                  <span className="text-sm font-medium text-slate-800">{caseData.merchant_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Category</span>
                  <span className="text-sm text-slate-800 capitalize">{caseData.merchant_context?.category?.replace('_', ' ') || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Location</span>
                  <span className="text-sm text-slate-800">{caseData.merchant_context?.location || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Typical Amount</span>
                  <span className="text-sm text-slate-800">{caseData.merchant_context?.typical_transaction_amount || 'Not available'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-slate-500">Txn Frequency</span>
                  <span className="text-sm text-slate-800">{caseData.merchant_context?.transaction_frequency || 'Not available'}</span>
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
            {caseData.related_activity?.length ? (
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
                    {caseData.related_activity.map(activity => (
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
          
          {recommendationQuery.isLoading && <LoadingState message="Loading agent recommendation..." />}
          {recommendationQuery.isError && (
            <ErrorState title="Recommendation unavailable" message="The investigation recommendation could not be loaded." onRetry={() => recommendationQuery.refetch()} />
          )}
          {recommendationQuery.data && <RecommendationCard recommendation={recommendationQuery.data} />}
          {!recommendationQuery.isLoading && !recommendationQuery.isError && !recommendationQuery.data && (
            <div className="rounded-lg border border-gray-200 bg-white p-5 text-sm text-slate-500">No recommendation is available for this case yet.</div>
          )}

          <ReviewActionPanel
            caseId={caseData.id}
            onSubmit={handleDecision}
            disabled={submitDecision.isSuccess}
            isSubmitting={submitDecision.isPending}
          />
          {submitDecision.isSuccess && (
            <div role="status" className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
              Decision submitted successfully. Case status is being refreshed.
            </div>
          )}
          {submitDecision.isError && (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              {submitDecision.error.message === 'Case already reviewed' ? 'Case already reviewed.' : getUserFacingApiMessage(submitDecision.error, 'Unable to submit the decision. Please try again.')}
            </div>
          )}

          {/* Evidence Pack */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-400" />
              Agent Evidence Pack
            </h3>
            {caseData.evidence?.length ? (
              <div className="space-y-3">
                {caseData.evidence.map(item => (
                  <EvidenceCard
                    key={item.id}
                    title={item.source}
                    description={item.summary}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 italic">No evidence has been attached to this case.</p>
            )}
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-4 uppercase tracking-wider flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" />
              Investigation Timeline
            </h3>
            {caseData.timeline?.length ? (
              <div className="mt-6">
                <InvestigationTimeline steps={caseData.timeline} />
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

export default CaseDetail;
