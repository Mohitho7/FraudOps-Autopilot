# Member 2 → Member 4: Data Contract Request

Status: **Batch 1 request.** Member 2 has created **no** SQLAlchemy models and
**no** Alembic migrations. Persistence is Member 4's. This document lists the
data Member 2 needs, derived only from `05_Database_Design_and_Data_Dictionary.docx`
and `06_Agent_System_Design.docx`.

---

## 1. Existing tables Member 2 reads (already in the design)

| Table | Fields Member 2 consumes | Used by |
| --- | --- | --- |
| `transactions` | `id`, `customer_id`, `merchant_id`, `amount`, `currency`, `timestamp`, `latitude`, `longitude`, `country`, `merchant_label`, `ip_address`, `device_id`, `status` | customer history, recent transactions, relationship search |
| `customers` | `id`, `name`, `email`, `country`, `risk_baseline`, `created_at` | `CustomerContext` |
| `merchants` | `id`, `name`, `category`, `country`, `expected_p50`, `expected_p95`, `expected_p99`, `operating_hours`, `daily_volume_baseline` | `MerchantContext` |
| `rule_results` | `id`, `transaction_id`, `rule_id`, `triggered`, `score`, `severity`, `reason`, `evidence_json` | `RuleResultsResult` — cited, never recomputed |
| `fraud_cases` | `id`, `primary_transaction_id`, `risk_score`, `severity`, `status`, `summary`, `recommendation`, `created_at` | `PriorCaseSummary`, case write-back |
| `evidence` | `id`, `case_id`, `source_type`, `source_ref`, `title`, `details_json`, `created_at` | evidence persistence |
| `case_entities` | `id`, `case_id`, `entity_type`, `entity_ref`, `relation_type` | `RelatedEntity` |
| `review_actions` | `id`, `case_id`, `reviewer_id`, `action`, `note`, `created_at` | `HumanDecision` |

Indexes already specified in the design (section 8) cover Member 2's read
patterns: `transactions(customer_id, timestamp)`,
`transactions(merchant_id, timestamp)`, `transactions(timestamp)`,
`rule_results(transaction_id)`, `case_entities(case_id, entity_type, entity_ref)`.

**Additional read need:** relationship search also matches on
`device_id` and `ip_address`. The design mentions devices and IP activity as
entities to link (`case_entities.entity_type`), and the indexing list does not
name those two columns. **Question for Member 4:** are
`transactions(device_id, timestamp)` and `transactions(ip_address, timestamp)`
indexed? Relationship analysis without them degrades to a scan.

## 2. Tables Member 2 needs that are not yet in the design

The design states that "investigations persist state including current step,
completed checks, findings, evidence references, recommendation, and human
outcome" (System Design addendum) and that state must allow "retries,
resume-after-failure behavior, and complete investigation replay" (Agent System
Design section 6). No such table is listed in the core table set.

**Request: one new table, `investigations`.** Proposed minimum columns, using
the naming and type conventions of the existing design:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` PK | matches `InvestigationState.investigation_id` |
| `transaction_id` | `UUID` FK → `transactions.id` | indexed |
| `case_id` | `UUID` NULL FK → `fraud_cases.id` | set by the case write tool |
| `customer_id` | `UUID` NULL FK → `customers.id` | |
| `merchant_id` | `UUID` NULL FK → `merchants.id` | |
| `risk_score` | `NUMERIC(5,2)` or `INT` | echo of Member 1's score, 0–100 |
| `severity` | `VARCHAR(20)` | `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` |
| `status` | `VARCHAR(20)` | `RUNNING`/`WAITING_HUMAN`/`COMPLETED`/`FAILED` |
| `trigger` | `VARCHAR(20)` | `RISK_THRESHOLD`/`REVIEWER_REQUEST` |
| `current_step` | `VARCHAR(40)` | resume point |
| `completed_steps` | `JSONB` | array of step names |
| `state_json` | `JSONB` | full `InvestigationState.to_dict()` checkpoint |
| `schema_version` | `VARCHAR(10)` | currently `"1.0"`; guards checkpoint compatibility |
| `retry_count` | `INT` | bounded retry accounting |
| `started_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |
| `completed_at` | `TIMESTAMPTZ` NULL | |
| `last_checkpoint_at` | `TIMESTAMPTZ` NULL | resume-after-failure |

**Question for Member 4:** may `state_json` hold the whole checkpoint, or
should the columns be normalised into `investigations` + `investigation_steps` +
`investigation_findings`? Member 2 works with either; the Pydantic model
serialises to a single JSON document, which is the simplest thing to support and
keeps replay exact.

**Request: agent step audit rows.** The audit trail in `Agent System Design`
section 12 must be queryable ("every investigation should produce an auditable
timeline"). `InvestigationState.activity` already carries the full timeline, so
it can live inside `state_json`. If Member 4 prefers a relational table, the
fields Member 2 would need are: `investigation_id`, `sequence`,
`step`, `status`, `summary`, `tool_name`, `input_refs` (JSONB), `output_refs`
(JSONB), `occurred_at`, `error`.

**Request: LangGraph checkpointer.** `InvestigationSettings.checkpoint_backend`
defaults to `memory` and is designed to become `postgres`. If Member 4 provides
a checkpointer, Member 2 will point LangGraph at it. Not required for Batch 2
start.

## 3. Mapping to existing tables Member 2 writes

Member 2 does **not** write these tables directly. It calls the write tools
`EvidenceWriter` / `CaseUpdater`, which Member 1 implements over Member 4's
tables:

| Member 2 field | Destination column |
| --- | --- |
| `EvidenceItem.source_type` | `evidence.source_type` |
| `EvidenceItem.source_ref` | `evidence.source_ref` |
| `EvidenceItem.title` | `evidence.title` |
| `EvidenceItem.details` | `evidence.details_json` |
| `RelatedEntity.entity_type / entity_ref / relation_type` | `case_entities.*` |
| `EvidencePack.summary` | `fraud_cases.summary` |
| `Recommendation.action` | `fraud_cases.recommendation` |
| `HumanDecision.action / reviewer_id / note / decided_at` | `review_actions.*` |

## 4. Enumerations Member 2 expects (must match the design)

* `fraud_cases.severity`: `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`
* `fraud_cases.status`: `OPEN` | `UNDER_REVIEW` | `CLEARED` | `CONFIRMED_FRAUD` | `ESCALATED`
* `transactions.status`: `NORMAL` | `FLAGGED` | `REVIEWED` | `CLEARED` | `CONFIRMED_FRAUD`
* `evidence.source_type`: `TRANSACTION` | `CUSTOMER` | `MERCHANT` | `RULE_RESULT` | `RELATIONSHIP` | `PRIOR_CASE` | `CALCULATION` (Member 2 writes only these values)
* `case_entities.entity_type`: `CUSTOMER` | `ACCOUNT` | `DEVICE` | `IP_ADDRESS` | `MERCHANT` | `TRANSACTION`
* `case_entities.relation_type`: `SHARED_DEVICE` | `SHARED_IP_ADDRESS` | `SHARED_ACCOUNT` | `SHARED_MERCHANT` | `LOCATION_OVERLAP` | `TEMPORAL_CLUSTER` | `LINKED_TRANSACTION`
* Member 2 only: `investigations.status` = `RUNNING` | `WAITING_HUMAN` | `COMPLETED` | `FAILED`

If Member 4 chooses different literals for `evidence.source_type` or
`case_entities.relation_type`, the enums in
`backend/app/schemas/investigation.py` must be updated in the same change.

## 5. Open questions for Member 4

1. Does an `investigations` table get created, and is `state_json` acceptable as
   the checkpoint column, or are normalised step/finding tables expected?
2. Are `transactions(device_id, ...)` and `transactions(ip_address, ...)`
   indexed for relationship analysis?
3. Which session/transaction boundary should the read tools use, and is a
   read-only session role available so the agent tools cannot write?
4. Does Member 4 provide the LangGraph PostgreSQL checkpointer, or does Member 2
   need to own that table?
5. Retention: `Agent System Design` requires complete investigation replay. Is
   `state_json` inside the standard retention window, or does the audit trail
   need its own policy?
