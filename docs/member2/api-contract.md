# Member 2 — API Contracts

Status: **Batch 1.** Both contracts are implemented as validated Pydantic
models and covered by tests. The HTTP routes that expose them are **not**
implemented in Batch 1 — Member 1 owns `app/api/`. The route shapes below are
the intended bindings and need team agreement before Member 1 or Member 3 codes
against them.

Source models:

* M1 → M2: `backend/app/schemas/investigation.py` → `InvestigationRequest`
* M2 → M3: `backend/app/schemas/investigation_result.py` → `InvestigationResponse`

---

## 1. Member 1 → Member 2 — `InvestigationRequest`

**Direction:** Member 1's risk engine hands the deterministic fraud result to
the investigation layer.

**Member 2 does not calculate the deterministic fraud score.** `risk_score` and
`severity` are echoed verbatim; no member-2 code path modifies, re-weights or
re-derives them.

### Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `transaction_id` | `UUID` | yes | Transaction that triggered the investigation |
| `risk_score` | `int` 0–100 | yes | Member 1 risk engine score. Echoed, never recomputed |
| `severity` | `Severity` | yes | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`, from Member 1 |
| `triggered_rules` | `list[RuleResultRecord]`, min 1 | yes | Rule results that fired, with reasons and evidence values |
| `case_id` | `UUID \| None` | no | Existing fraud case, when Member 1 already created one |
| `customer_id` | `UUID \| None` | no | Derived from `transaction_context` when omitted |
| `merchant_id` | `UUID \| None` | no | Derived from `transaction_context` when omitted |
| `transaction_context` | `TransactionContext \| None` | no | Transaction snapshot (amount, currency, time, coordinates, device, IP) |
| `context_signals` | `list[ContextSignal]` | no | Deterministic signals from Member 1's context enricher (doc 06 `risk_signals`) |
| `trigger` | `InvestigationTrigger` | no (default `RISK_THRESHOLD`) | `RISK_THRESHOLD` or `REVIEWER_REQUEST` |
| `requested_by` | `str \| None` | no | Reviewer/service id for the audit trail. Authorisation is Member 1's job |

`RuleResultRecord` mirrors the Rule Result Contract (Backend Specification
section 6): `rule_id`, `rule_name`, `triggered`, `score`, `severity`, `reason`,
`evidence`.

`TransactionContext` mirrors the `transactions` table (Database Design
section 4): `transaction_id`, `customer_id`, `merchant_id`, `amount` (Decimal),
`currency`, `timestamp` (tz-aware), `latitude`, `longitude`, `country`,
`merchant_label`, `ip_address`, `device_id`, `status`.

### Validation rules

* `extra="forbid"` on every model — unknown fields are rejected, so a contract
  change cannot pass silently.
* `risk_score` in `[0, 100]`; `latitude` in `[-90, 90]`; `longitude` in
  `[-180, 180]`; `amount > 0`.
* `currency` matches `^[A-Z]{3}$`.
* `timestamp` and `context_signals.observed_at` must be timezone aware
  (the database uses `TIMESTAMPTZ`).
* `latitude` and `longitude` must be supplied together.
* `triggered_rules` must contain at least one entry: an investigation always
  starts from a deterministic signal.
* `transaction_context.transaction_id` must equal `transaction_id`, and the
  context's customer/merchant ids must match the request when both are given.
* Frozen models: a request cannot be mutated after validation.

### Valid payload

```json
{
  "transaction_id": "0f3d1c1e-6b6a-4f4b-9f2a-1d2c3b4a5e6f",
  "customer_id": "6c1f0d2a-7b3c-4d5e-8f90-1a2b3c4d5e6f",
  "merchant_id": "9a8b7c6d-5e4f-4a3b-8c9d-0e1f2a3b4c5d",
  "case_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "risk_score": 94,
  "severity": "CRITICAL",
  "triggered_rules": [
    {
      "rule_id": "unusual_amount",
      "rule_name": "Unusual Transaction Amount",
      "triggered": true,
      "score": 35,
      "severity": "HIGH",
      "reason": "Amount is 434.8x customer baseline",
      "evidence": {
        "amount": "1000000.00",
        "customer_average": "2300.00",
        "merchant_p95": "6500.00"
      }
    }
  ],
  "context_signals": [
    {
      "signal_type": "customer_amount_ratio",
      "description": "Amount is 434.8x the customer baseline",
      "value": 434.8,
      "severity": "HIGH",
      "source": "context_enricher:customer_history"
    }
  ]
}
```

### Invalid payloads (all rejected)

```json
{"transaction_id": "0f3d...", "risk_score": 101, "severity": "CRITICAL", "triggered_rules": [...]}
{"transaction_id": "0f3d...", "risk_score": 94, "severity": "EXTREME", "triggered_rules": [...]}
{"transaction_id": "0f3d...", "risk_score": 94, "severity": "HIGH", "triggered_rules": []}
{"transaction_id": "0f3d...", "risk_score": 94, "severity": "HIGH"}
{"risk_score": 94, "severity": "HIGH", "triggered_rules": [...]}
{"transaction_id": "0f3d...", "risk_score": 94, "severity": "HIGH", "triggered_rules": [...], "frontend_layout": "danger"}
```

### Startup policy

`should_start_investigation(request, settings)` in
`app/services/investigation_service.py` is the only place the threshold is
applied:

* `severity >= FRAUDOPS_INVESTIGATION_MIN_AUTO_INVESTIGATION_SEVERITY`
  (default `HIGH`) → automatic investigation.
* `trigger = REVIEWER_REQUEST` → always allowed.
* `LOW` / `MEDIUM` below the threshold →
  `InvestigationNotRequiredError`; the case stays in monitor/aggregate mode.

## 2. Member 2 → Member 3 — `InvestigationResponse`

**Direction:** the reviewer console renders backend truth. The frontend must
not recompute risk, severity or fraud logic locally.

### Fields

| Field | Type | Description |
| --- | --- | --- |
| `investigation_id` | `UUID` | Investigation instance id |
| `transaction_id` | `UUID` | Transaction under investigation |
| `case_id` | `UUID \| None` | Fraud case id, when one exists |
| `status` | `InvestigationStatus` | `RUNNING` / `WAITING_HUMAN` / `COMPLETED` / `FAILED` |
| `risk_score` | `int` 0–100 | Echoed from Member 1 |
| `severity` | `Severity` | Echoed from Member 1 |
| `triggered_rules` | `list[RuleResultRecord]` | Echoed, so the UI can show which rules fired |
| `findings` | `list[InvestigationFinding]` | **Findings** — behavioral, business, relationship |
| `evidence` | `list[EvidenceItem]` | **Evidence** — each with `source_ref` and `claim_kind` |
| `related_entities` | `list[RelatedEntity]` | Linked customers, devices, IPs, merchants, transactions |
| `recommendation` | `Recommendation \| None` | **Recommendation** — action, confidence, rationale, evidence refs, `requires_human_review` |
| `confidence` | `float \| None` 0–1 | **Confidence** of the investigation overall |
| `activity_timeline` | `list[InvestigationActivity]` | **Timeline** — ordered structured events, no chain-of-thought |
| `human_decision` | `HumanDecision \| None` | **Human decision** — action, reviewer, note, time |
| `error` | `InvestigationError \| None` | Failure detail when `status = FAILED` |
| `started_at` / `updated_at` / `completed_at` | `datetime` | Lifecycle timestamps, tz-aware |
| `requires_human_review` | `bool` (computed) | Derived so the console does not re-implement the handoff policy |

### Explainability contract

Every evidence item and finding carries a `ClaimKind`:

| `claim_kind` | Meaning | Source |
| --- | --- | --- |
| `OBSERVED_FACT` | A stored value | Database record |
| `CALCULATED_METRIC` | A computed value | Python / SQL |
| `RULE_RESULT` | A deterministic rule outcome | Member 1 |
| `AGENT_INTERPRETATION` | The model's reading of the facts | LLM |
| `RECOMMENDATION` | The advisory action | LLM + policy |

The console renders the first three as hard evidence and the last two as agent
output, satisfying "Facts, evidence and AI recommendations must be visually
distinguishable" (Frontend Specification, UX rules).

### Example response

```json
{
  "investigation_id": "8f0a6d2c-1b3e-4f5a-9c7d-2e1f0a9b8c7d",
  "transaction_id": "0f3d1c1e-6b6a-4f4b-9f2a-1d2c3b4a5e6f",
  "case_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "status": "WAITING_HUMAN",
  "risk_score": 96,
  "severity": "CRITICAL",
  "triggered_rules": [
    {
      "rule_id": "unusual_amount",
      "rule_name": "Unusual Transaction Amount",
      "triggered": true,
      "score": 35,
      "severity": "HIGH",
      "reason": "Amount is 434.8x customer baseline",
      "evidence": {"amount": "1000000.00", "customer_average": "2300.00"}
    }
  ],
  "findings": [
    {
      "finding_id": "2b1c0d9e-8f7a-4b6c-9d5e-3a2b1c0d9e8f",
      "category": "BEHAVIORAL",
      "title": "Amount is 434.8x customer average",
      "summary": "The customer normally spends between INR 500 and INR 5,000.",
      "confidence": 0.93,
      "severity_impact": "CRITICAL",
      "metrics": {"amount_multiple_of_customer_average": 434.8},
      "evidence_refs": ["evidence:4c5d6e7f-8a9b-4c0d-9e1f-2a3b4c5d6e7f"]
    }
  ],
  "evidence": [
    {
      "evidence_id": "4c5d6e7f-8a9b-4c0d-9e1f-2a3b4c5d6e7f",
      "source_type": "RULE_RESULT",
      "source_ref": "rule_result:unusual_amount",
      "claim_kind": "RULE_RESULT",
      "title": "Unusual amount rule triggered",
      "details": {"amount": "1000000.00", "customer_average": "2300.00"},
      "confidence": null,
      "observed_at": "2026-09-30T10:30:00Z",
      "reference": "evidence:4c5d6e7f-8a9b-4c0d-9e1f-2a3b4c5d6e7f"
    }
  ],
  "related_entities": [
    {
      "entity_type": "DEVICE",
      "entity_ref": "device:abc-123",
      "relation_type": "SHARED_DEVICE",
      "label": "Shared device",
      "risk_note": "Also used by a previously flagged customer.",
      "related_case_id": null
    }
  ],
  "recommendation": {
    "action": "HOLD_FOR_REVIEW",
    "confidence": 0.94,
    "rationale": "Amount is far outside both the customer baseline and the merchant profile.",
    "evidence_refs": ["evidence:4c5d6e7f-8a9b-4c0d-9e1f-2a3b4c5d6e7f"],
    "requires_human_review": true
  },
  "confidence": 0.92,
  "activity_timeline": [
    {
      "sequence": 0,
      "step": "LOAD_STATE",
      "status": "COMPLETED",
      "summary": "Investigation started for transaction 0f3d1c1e-... with 2 triggered rule result(s)",
      "tool_name": null,
      "occurred_at": "2026-09-30T11:20:01Z",
      "error": null
    },
    {
      "sequence": 1,
      "step": "CALL_TOOL",
      "status": "COMPLETED",
      "summary": "Loaded 90-day customer history (42 transactions)",
      "tool_name": "get_customer_history",
      "occurred_at": "2026-09-30T11:20:01Z",
      "error": null
    }
  ],
  "human_decision": null,
  "error": null,
  "started_at": "2026-09-30T11:20:01Z",
  "updated_at": "2026-09-30T11:20:04Z",
  "completed_at": null,
  "requires_human_review": true
}
```

### Vocabulary shared with the database

`Severity` (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`), case `status`
(`OPEN`/`UNDER_REVIEW`/`CLEARED`/`CONFIRMED_FRAUD`/`ESCALATED`),
`evidence.source_type`, `case_entities.entity_type` and `relation_type`, and the
reviewer actions `CLEAR` / `CONFIRM_FRAUD` / `ESCALATE` / `MARK_REVIEWED` come
from the Database Design and Frontend Specification documents so that the API
and the schema stay aligned.

## 3. Intended HTTP bindings (not implemented in Batch 1)

| Method | Endpoint | Owner | Payload |
| --- | --- | --- | --- |
| POST | `/api/investigations` | Member 1 route, Member 2 payload | `InvestigationRequest` in, `InvestigationResponse` out |
| GET | `/api/investigations/{investigation_id}` | Member 1 route, Member 2 payload | `InvestigationResponse` |
| POST | `/api/investigations/{investigation_id}/resume` | Member 1 route, Member 2 payload | `InvestigationResponse` |
| GET | `/api/cases/{id}/investigation` | Member 1 route, Member 2 payload | `InvestigationResponse` |

Member 1 owns the router, authentication and HTTP status codes. Member 2 owns
the body models and the service call.
