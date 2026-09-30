# Member 2 — Investigation Tool Contract

Status: **Batch 1.** Every tool below exists as a `Protocol` (the contract) plus
a typed input/output model. The implementations are stubs that raise
`ToolNotImplementedError`; no database query runs yet.

Guardrails taken from the System Design addendum ("Agent Tooling") and the
Agent System Design (section 7):

* Agents access data through narrow, approved tools — never arbitrary database
  access.
* Every tool call is logged with input identifiers and output references
  (`ToolCallRecord`, `InvestigationState.record_activity`).
* Tools return structured data that preserves the source record identifiers
  used as evidence (`<kind>:<identifier>` references).

---

## 1. Tool inventory

| Interface | Method | Scope | Output type | Implementation owner |
| --- | --- | --- | --- | --- |
| `CustomerHistoryTool` | `get_customer_history(customer_id, time_window=None)` | one customer | `CustomerHistory` | Member 4 (read layer) |
| `RecentTransactionsTool` | `get_recent_transactions(customer_id=..., merchant_id=..., time_window=None, limit=100)` | exactly one subject | `RecentTransactionSet` | Member 4 |
| `MerchantProfileTool` | `get_merchant_profile(merchant_id)` | one merchant | `MerchantContext` | Member 4 |
| `RelatedEntitiesTool` | `get_related_entities(transaction_id, *, limit=50)` | one transaction | `list[RelatedEntity]` | Member 4 |
| `RuleResultsTool` | `get_rule_results(transaction_id)` | one transaction | `RuleResultsResult` | Member 4 |
| `PriorCasesTool` | `get_prior_cases(customer_id=..., entity_ref=..., limit=20)` | exactly one scope | `list[PriorCaseSummary]` | Member 4 |
| `EvidenceWriter` | `save_evidence(case_id, evidence)` | one case | `list[UUID]` | Member 1 (case/evidence service) |
| `CaseUpdater` | `create_or_update_case(...)` | one investigation | `UUID` | Member 1 (case service) |

All methods are `async` so the workflow never blocks the event loop on I/O.

### Naming map

The Batch 1 brief used the aliases below; the implementation follows
`Agent System Design` section 7, which is the documentation source of truth.

| Brief alias | Implemented interface |
| --- | --- |
| `get_customer_history` | `get_customer_history` |
| `get_transaction_history` | `get_recent_transactions` |
| `get_merchant_context` | `get_merchant_profile` |
| `get_related_entities` | `get_related_entities` |
| `get_previous_cases` | `get_prior_cases` |
| — | `get_rule_results` (needed to cite Member 1's results) |

### Deliberately absent tools

| Tool from the docs | Why it is not declared by Member 2 |
| --- | --- |
| `calculate_geo_distance` | Distance/elapsed/implied-speed is Member 1's impossible-travel rule. Declaring it here would duplicate deterministic fraud logic. Member 1's `rule_results.evidence_json` already carries the computed values, which the investigation cites. |
| `send_notification` | Notification delivery is Member 4's. The investigation layer only sets `status`, and Member 4's threshold logic sends the SES/SNS message. |

## 2. Input and output types (`app/agents/tools/types.py`)

| Type | Purpose | Key fields |
| --- | --- | --- |
| `TimeWindow` | Half-open time range for history queries | `start`, `end` (both tz-aware, `start < end`) |
| `TransactionSummary` | Read-only transaction projection | `transaction_id`, `customer_id`, `merchant_id`, `amount` (Decimal), `currency`, `timestamp`, `country`, coordinates, `ip_address`, `device_id` |
| `AmountStatistics` | Deterministic amount distribution | `sample_size`, `minimum`, `maximum`, `mean`, `median`, `p95`, `p99`, `standard_deviation`, `has_baseline` |
| `CustomerContext` | Profile + baseline | `customer_id`, `country`, `risk_baseline`, `account_created_at`, `default_currency`, `amount_statistics`, `transaction_count`, `last_transaction_at` |
| `CustomerHistory` | `get_customer_history` result | `customer_id`, `window`, `context`, `transactions`, `recent_review_outcomes`, `reference` |
| `OperatingHours` | Parsed `merchants.operating_hours` | `opens_at`, `closes_at`, `contains(time)` (handles overnight windows) |
| `MerchantObservedStatistics` | Observed merchant distribution | `window`, `transaction_count`, `amount_statistics`, `average_daily_volume` |
| `MerchantContext` | Business profile | `merchant_id`, `category`, `subcategory`, `country`, `expected_p50/p95/p99`, `operating_hours`, `daily_volume_baseline`, `observed`, `reference` |
| `RecentTransactionSet` | `get_recent_transactions` result | `customer_id` **xor** `merchant_id`, `window`, `transactions`, `amount_statistics` |
| `RelatedEntitiesResult` | `get_related_entities` result | `transaction_id`, `entities`, `generated_at`, `reference`, `entity_count` |
| `RuleResultsResult` | `get_rule_results` result | `transaction_id`, `results`, `reference`, `triggered`, `highest_severity` |
| `PriorCaseSummary` | One previous case | `case_id`, `transaction_id`, `severity`, `risk_score`, `status`, `summary`, `recommendation`, `created_at`, `reference` |
| `PriorCasesResult` | `get_prior_cases` result | `customer_id` **xor** `entity_ref`, `cases`, `reference` |

All models use `extra="forbid"` and `frozen=True`: a tool cannot silently
overwrite a field, and a stored record cannot be edited by the agent.

## 3. Deterministic vs. AI boundary

Everything a tool returns is a **fact or a deterministic calculation**:

```
transactions / merchants / customers / rule_results  →  stored values
baselines, percentiles, counts, rate of change      →  Python or SQL
entity link counts                                   →  bounded SQL lookup
distance, elapsed time, implied speed               →  Member 1's rule, cited not recomputed
```

The language model receives these values inside a structured request
(`CustomerHistory`, `MerchantContext`, `RelationshipAnalysisRequest`) and may
only *phrase* them. Amounts are passed to the analyzers as strings precisely so
the model cannot re-parse or alter them.

## 4. Audit requirement

Every call must be wrapped like this (Batch 2 responsibility):

```python
record = ToolCallRecord.started(
    tool_name="get_customer_history",
    step=InvestigationStep.CALL_TOOL,
    input_refs=[f"customer:{customer_id}"],
)
state.record_activity(
    step=InvestigationStep.CALL_TOOL,
    status=ToolStatus.COMPLETED,
    summary=f"Loaded {history.context.transaction_count} transactions",
    tool_name="get_customer_history",
)
```

`output_refs` carries the returned `reference` values so the audit trail links
each call to the records it produced.

## 5. Failure policy (contract)

| Failure | Expected behaviour (Agent System Design section 13) |
| --- | --- |
| Tool timeout | Retry within `FRAUDOPS_INVESTIGATION_MAX_TOOL_RETRIES`, record the failure, continue with independent checks |
| Database read failure | Record `InvestigationError`; never mark the step complete |
| Non-conforming tool output | Rejected by the Pydantic model at the boundary (`validate_output` node) |
| Contradictory findings | Mark the investigation as requiring human review |
| Notification failure | Out of scope for Member 2; must not invalidate a persisted decision |

## 6. Status summary

| Item | Status |
| --- | --- |
| Tool protocols | **Implemented** |
| Tool input/output models and their validation | **Implemented** |
| `ToolCallRecord` audit structure | **Implemented** |
| Database-backed tool implementations | **Not implemented** — requires Member 4's persistence layer |
| Write-tool implementations (`save_evidence`, `create_or_update_case`) | **Not implemented** — owned by Member 1 |
