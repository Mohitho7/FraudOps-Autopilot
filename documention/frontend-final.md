# FraudOps Autopilot Frontend Final Documentation

## Frontend Overview

FraudOps Autopilot is a React reviewer console for investigating suspicious transactions, reviewing structured evidence and agent recommendations, and recording an explicit human decision.

## Architecture

```text
User -> React pages/components -> React Query hooks -> service layer -> endpoint configuration -> API or isolated mock
```

All backend endpoint mappings are intentionally empty. Services use the existing mock data until backend contracts are confirmed.

## Main Pages

- `/login`: redirects to the dashboard; the current demo opens directly without a login step
- `/dashboard`: command center metrics and flagged transactions
- `/transactions`: searchable, filterable transaction queue
- `/transactions/:id`: transaction facts and investigation context
- `/cases`: case queue
- `/cases/:id`: risk, rules, context, evidence, timeline, recommendation, and decision
- `/review-history`: completed human review audit records
- `/network`: related entity visualization and accessible relationship table
- `/rules`: read-only rule catalog
- `/rules/simulation`: service-backed rule simulation with structural validation

## Reusable Components

`PageContainer`, `DataTable`, `RiskBadge`, `StatCard`, `LoadingState`, `ErrorState`, `EmptyState`, `RuleResultCard`, `EvidenceCard`, `InvestigationTimeline`, `RecommendationCard`, and `ReviewActionPanel` are shared across workflow screens.

## Human-in-the-Loop

**AI recommends. Human decides.** The recommendation card only displays structured agent output. The reviewer must explicitly choose Approve, Reject, or Escalate, enter optional notes, and confirm the action. Duplicate submissions are rejected by the service layer.

## Security Boundaries

The frontend does not calculate fraud scores, evaluate fraud rules, run agent reasoning, expose prompts, or display chain-of-thought. `VITE_API_BASE_URL` is the only permitted frontend environment variable. Authentication is bypassed for the demo and remains mock/local-storage based; it is not production authentication.

## Mock Mode and Backend Integration

Mock mode exists because the backend endpoint paths and response contracts are pending. To integrate the backend, populate `frontend/src/config/apiEndpoints.ts` with confirmed mappings and update service response adapters only where the confirmed schema differs from the shared TypeScript models.

## Data Contracts

Current contracts are defined in `frontend/src/types/`: `Transaction`, `FraudCase`, `RuleResult`, `EvidenceItem`, `CustomerContext`, `MerchantContext`, `RelatedActivity`, `AgentRecommendation`, `ReviewRecord`, `NetworkNode`, `NetworkEdge`, `FraudRule`, and `RuleSimulationResult`. No duplicate page-local models are used for these boundaries.

## Demo Flow

```text
LOGIN -> COMMAND CENTER -> TRANSACTION -> CASE -> RISK -> RULES -> CONTEXT -> RELATED ACTIVITY -> TIMELINE -> EVIDENCE -> RECOMMENDATION -> HUMAN DECISION -> REVIEW HISTORY -> NETWORK
```

## Final Freeze

After Batch 7/8 verification, only critical bug fixes should be made. New backend features, fraud algorithms, agent infrastructure, database work, and unrelated UI features are outside the frozen frontend scope.
