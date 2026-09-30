# Member 2 — Agentic Investigation System: Architecture

Status: **Batch 1 (foundation) complete.** Contracts, state, tool interfaces and
the service boundary exist. No investigation logic, no LangGraph graph and no
LLM calls exist yet.

Branch: `feature/member2-agentic-investigation`

---

## 1. What Member 2 owns

| Area | Owner statement | Where it lives |
| --- | --- | --- |
| Investigation orchestration | Decides which checks run, in what order, and when evidence is sufficient | `backend/app/agents/graph/` |
| Investigation state | Stateful, checkpointable, replayable investigation record | `backend/app/agents/graph/state.py` |
| Behavioral analysis | Is the transaction abnormal **for this customer**? | `backend/app/agents/behavioral/` |
| Business context analysis | Is the amount plausible **for this merchant/category**? | `backend/app/agents/business/` |
| Relationship analysis | Which customers, devices, IPs, merchants are linked? | `backend/app/agents/relationship/` |
| Evidence building | Structured evidence pack + analyst summary | `backend/app/agents/evidence/` |
| Recommendation | Advisory `ALLOW / MONITOR / HOLD_FOR_REVIEW / ESCALATE` | `backend/app/agents/recommendation/` |
| Approved tool interfaces | Least-privilege read tools the workflow may call | `backend/app/agents/tools/` |
| Agent audit trail | Ordered, structured activity timeline (no chain-of-thought) | `InvestigationState.activity` |
| Human handoff | `WAITING_HUMAN` status and reviewer decision payload | `InvestigationStatus.WAITING_HUMAN`, `HumanDecision` |
| Contracts | M1→M2 input, M2→M3 output | `backend/app/schemas/investigation.py`, `backend/app/schemas/investigation_result.py` |
| Service boundary | `start_investigation` / `get_investigation` / `resume_investigation` | `backend/app/services/investigation_service.py` |

## 2. What Member 2 does NOT own

* **Fraud rule engine** — velocity, unusual amount, impossible travel, merchant
  category rules, risk scoring, severity classification. That is Member 1
  (`backend/app/rules/`, `risk_service`). Member 1's output is an immutable
  input to Member 2.
* **FastAPI application, routes, auth (JWT)** — Member 1.
* **React reviewer console, dashboard, case UI, fraud graph rendering** — Member 3.
* **SQLAlchemy models, Alembic migrations, indexes, seed data** — Member 4.
* **AWS SES/SNS notification delivery** — Member 4. The investigation layer
  never sends a notification; it only sets a status the notification threshold
  logic reads.
* **PostgreSQL connectivity** — Member 4. Member 2 consumes read tools.

The deterministic/AI split is enforced structurally: the LLM never receives a
prompt that asks it to compute an amount, a distance, a percentile or a count.
Those arrive as typed, already-computed values (`InvestigationFinding.metrics`,
`EvidenceItem.details`) produced by tools and Python.

## 3. Module layout

```
backend/
├── app/
│   ├── agents/                      # Member 2 core
│   │   ├── analysis.py              # shared AnalysisOutcome for the 3 capabilities
│   │   ├── config.py                # FRAUDOPS_INVESTIGATION_* settings
│   │   ├── behavioral/analyzer.py
│   │   ├── business/analyzer.py
│   │   ├── relationship/analyzer.py
│   │   ├── evidence/builder.py
│   │   ├── recommendation/agent.py
│   │   ├── graph/
│   │   │   ├── state.py             # InvestigationState
│   │   │   ├── nodes.py             # node vocabulary + transition data
│   │   │   └── workflow.py          # build_investigation_graph() — NotImplemented
│   │   ├── tools/                   # approved tool protocols + stubs
│   │   └── prompts/investigation.py # narration templates only
│   ├── schemas/
│   │   ├── investigation.py         # M1 -> M2 contract + shared enums
│   │   └── investigation_result.py  # M2 -> M3 contract
│   └── services/investigation_service.py
├── tests/agents/                    # Member 2 contract tests
└── requirements.txt / pyproject.toml
```

`backend/app/agents/` follows the backend layout defined in the Backend
Specification (section 3), where the agentic layer is `app/agents/`. The flat
file names suggested there (`graph.py`, `history.py`, `business_context.py`,
`relationships.py`, `evidence.py`) are grouped into packages so that the three
capabilities, the state and the tools stay separable.

## 4. Investigation flow (planned, not implemented)

```
Member 1 risk engine
        │  InvestigationRequest (transaction_id, risk_score, severity,
        │  triggered_rules, context_signals, transaction_context)
        ▼
InvestigationService.start_investigation
        │  policy check: severity >= configured threshold, or reviewer request
        ▼
InvestigationState (RUNNING, current_step = LOAD_STATE)
        ▼
LangGraph workflow
   load_state → check_evidence ── insufficient ─→ select_next_check
                                              → call_tool → validate_output
                                              → persist_finding → check_evidence
                              ── sufficient ────→ evidence_build
                                                  → recommendation
                                                  → human_handoff (policy)
                                                  → complete
        ▼
InvestigationState.to_response() → Member 3 console
```

`InvestigationState` is a Pydantic model, which LangGraph accepts as a state
schema, and `to_dict()` / `from_dict()` give the plain-dict form needed for
checkpoints and for Member 4's `investigations.state_json` column.

## 5. Resume, retry and failure semantics (contract only)

* `current_step` + `completed_steps` make each step idempotent, so a retried
  investigation does not repeat completed work.
* `retry_count` and `InvestigationError.retryable` carry the bounded-retry
  policy from `InvestigationSettings.max_tool_retries`.
* `last_checkpoint_at` records the resume point.
* A failed step must be recorded in `activity` with `status="FAILED"`; a step is
  never reported as complete when its write failed.
* `LLM unavailable` is a supported state, not an error: `NarrativeSource`
  records whether a summary was templated in Python or model-narrated, and the
  investigation still completes with `LLM_ASSISTED` disabled.

## 6. Integration points

| Partner | Direction | Artefact | Status |
| --- | --- | --- | --- |
| Member 1 | → Member 2 | `InvestigationRequest` | Contract defined, needs Member 1's confirmation |
| Member 1 | Member 2 → | `EvidenceWriter`, `CaseUpdater` protocols (implemented in Member 1's case service) | Interface only |
| Member 3 | Member 2 → | `InvestigationResponse` | Contract defined, needs Member 3's confirmation |
| Member 4 | → Member 2 | Read tools over `transactions`, `customers`, `merchants`, `rule_results`, `fraud_cases` | Requested, see `data-contract.md` |
| Member 4 | Member 2 → | Persisted `investigations` / `evidence` / agent-step rows, LangGraph checkpointer | Requested, see `data-contract.md` |

## 7. Batch 2 prerequisites

1. `langgraph` and `openai` added to `backend/requirements.txt`.
2. Read tools implemented against Member 4's persistence layer.
3. `build_investigation_graph()` implemented with the node set in
   `app/agents/graph/nodes.py` and the edges in `app/agents/graph/workflow.py`.
4. The three capabilities implemented against the deterministic tool output.
5. A persistent `InvestigationService` replacing the in-memory stub.
