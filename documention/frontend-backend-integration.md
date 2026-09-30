# Frontend/Backend Integration Contract

Batch 6 keeps all backend endpoint paths empty. The frontend uses the service layer and isolated mocks until the backend team supplies confirmed paths and response contracts.

## Endpoint Placeholders

| Feature | Method | Endpoint | Status |
|---|---|---|---|
| Login | POST | `` | Pending backend |
| Dashboard | GET | `` | Pending backend |
| Transactions | GET | `` | Pending backend |
| Transaction detail | GET | `` | Pending backend |
| Cases | GET | `` | Pending backend |
| Case detail | GET | `` | Pending backend |
| Recommendation | GET | `` | Pending backend |
| Decision | POST | `` | Pending backend |
| Review history | GET | `` | Pending backend |
| Network | GET | `` | Pending backend |
| Rules | GET | `` | Pending backend |
| Rule simulation | POST | `` | Pending backend |

Mappings live in `frontend/src/config/apiEndpoints.ts`. Empty values must remain empty until confirmed by the backend team.

## Frontend Expects

The following existing TypeScript models are the source of truth for the current frontend boundary:

| Response | TypeScript model | Status |
|---|---|---|
| Transaction | `frontend/src/types/transaction.ts` -> `Transaction`, `PaginatedTransactions` | Confirmed by current UI/mock contract |
| Case | `frontend/src/types/case.ts` -> `FraudCase`, `PaginatedCases` | Confirmed by current UI/mock contract |
| Rule result | `frontend/src/types/rule.ts` -> `RuleResult` | Confirmed by current UI/mock contract |
| Evidence | `frontend/src/types/evidence.ts` -> `EvidenceItem` | Confirmed by current UI/mock contract |
| Recommendation | `frontend/src/types/recommendation.ts` -> `AgentRecommendation` | Confirmed by current UI/mock contract; backend confirmation pending |
| Review decision/history | `frontend/src/types/review.ts` -> `DecisionPayload`, `ReviewRecord`, `PaginatedReviews` | Confirmed by current UI/mock contract; backend confirmation pending |
| Network | `frontend/src/types/network.ts` -> `FraudNetworkData`, `NetworkNode`, `NetworkEdge` | Confirmed by current UI/mock contract; backend confirmation pending |
| Rule catalog | `frontend/src/types/rule.ts` -> `FraudRule` | Pending backend confirmation |
| Rule simulation | `frontend/src/types/rule.ts` -> `RuleSimulationInput`, `RuleSimulationResult` | Pending backend confirmation |

The frontend displays backend-provided risk scores, recommendations, rule results, and simulation results. It does not calculate them.

## Error Contract

`frontend/src/types/api.ts` defines these categories: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `SERVER_ERROR`, `NETWORK_ERROR`, `TIMEOUT`, `API_NOT_CONFIGURED`, and `UNKNOWN_ERROR`.

The API client rejects empty endpoints before making a request. Services choose mock data when their mapping is empty. Pages expose friendly error states and do not display raw stack traces.

## Authentication Limitation

Authentication currently uses the existing mock login and local browser session storage. When the login mapping is supplied, `authApi` will call the configured endpoint and the API client will attach the stored bearer token. This frontend is not claiming production-grade authentication while mock/local-storage mode remains active.

## Backend Handoff Checklist

The backend team should provide confirmed endpoint paths, HTTP methods, authentication requirements, pagination/filter semantics, status codes, error bodies, and response examples for each row above. Any response changes should update the existing TypeScript models rather than creating duplicate frontend definitions.
