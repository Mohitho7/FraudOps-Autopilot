# Frontend/Backend Handoff

**All real backend endpoint paths remain EMPTY by design.** Do not populate the table until the backend team confirms each contract.

| Feature | Method | Endpoint | Request | Response | Status |
|---|---|---|---|---|---|
| Login | POST | EMPTY | `LoginCredentials` | `AuthResponse` | Pending |
| Dashboard | GET | EMPTY | None | `DashboardSummary` | Pending |
| Transactions | GET | EMPTY | `TransactionFilters` | `PaginatedTransactions` | Pending |
| Transaction detail | GET | EMPTY | Transaction ID | `Transaction` | Pending |
| Cases | GET | EMPTY | `CaseFilters` | `PaginatedCases` | Pending |
| Case detail | GET | EMPTY | Case ID | `FraudCase` | Pending |
| Recommendation | GET | EMPTY | Case ID | `AgentRecommendation` | Pending |
| Decision | POST | EMPTY | `DecisionPayload` | Review result | Pending |
| Review history | GET | EMPTY | `ReviewFilters` | `PaginatedReviews` | Pending |
| Network | GET | EMPTY | Case ID | `FraudNetworkData` | Pending |
| Rules | GET | EMPTY | None | `FraudRule[]` | Pending |
| Rule simulation | POST | EMPTY | `RuleSimulationInput` | `RuleSimulationResult` | Pending |

## Existing TypeScript Contracts

- Transaction: `frontend/src/types/transaction.ts` (`Transaction`, `TransactionFilters`, `PaginatedTransactions`)
- Case: `frontend/src/types/case.ts` (`FraudCase`, `CaseFilters`, `PaginatedCases`)
- Rule result: `frontend/src/types/rule.ts` (`RuleResult`)
- Evidence: `frontend/src/types/evidence.ts` (`EvidenceItem`)
- Customer and merchant context: `frontend/src/types/case.ts` (`CustomerContext`, `MerchantContext`)
- Related activity: `frontend/src/types/case.ts` (`RelatedActivity`)
- Recommendation: `frontend/src/types/recommendation.ts` (`AgentRecommendation`, `RecommendationReason`)
- Review decision/history: `frontend/src/types/review.ts` (`DecisionPayload`, `ReviewRecord`, `PaginatedReviews`)
- Network: `frontend/src/types/network.ts` (`NetworkNode`, `NetworkEdge`, `FraudNetworkData`)
- Rules and simulation: `frontend/src/types/rule.ts` (`FraudRule`, `RuleSimulationInput`, `RuleSimulationResult`)

## Backend Must Confirm

Endpoint paths, HTTP methods, authentication and reviewer roles, request schemas, response schemas, pagination, filtering, status codes, error body format, recommendation status values, review decision semantics, network relationship fields, rule catalog fields, and simulation result fields.

## Security Boundary

Do not send secrets to the frontend. The client only supports a safe base URL and bearer-token abstraction. Mock authentication currently uses local browser storage and must be replaced or connected to the backend authentication contract before production use.
