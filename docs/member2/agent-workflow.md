# Member 2 - Agentic Investigation System: Workflow (Batch 2)

Status: **Batch 2 implemented.** Context loading runs end to end on a real
LangGraph graph with checkpoint and resume. Analysis, evidence synthesis,
recommendation and human handoff are **not** part of this batch.

This document records what the engine does, how resume works, which contract
gaps are open, and what is deliberately not implemented. See `architecture.md`
for the module boundaries and the Batch 1 contract.

## 1. The Batch 2 graph

Compiled by `build_investigation_graph(toolset, settings, checkpoint_store)` in
`app/agents/graph/workflow.py`:

```
START
  → initialize_investigation       (LOAD_STATE)
  → validate_investigation_input   (VALIDATE_OUTPUT)   get_rule_results
  → load_transaction_context       (CALL_TOOL)         request snapshot, else
                                                                get_recent_transactions
  → load_customer_context          (CALL_TOOL)         get_customer_history
  → load_merchant_context          (CALL_TOOL)         get_merchant_profile
  → load_relationship_context      (CALL_TOOL)         get_related_entities
  → finalize_investigation         (COMPLETE)
  → END
```

Every node returns a partial state update; LangGraph merges it. The graph's only
outbound dependency is the `InvestigationToolset` it is compiled with, which is
how the least-privilege guardrail survives wiring: there is no database handle, no
HTTP client and no language-model client on the graph.

`finalize_investigation` sets `status=COMPLETED`. That is the honest end state for
this batch: the deterministic context is loaded and nothing else has happened, so
no finding, no evidence and no recommendation is attached. The console receives
context, not a conclusion.

### Dispatch is not a fixed chain

Routing goes through one function, `route_next_node(state)`, which returns the
first node that has no `COMPLETED` activity entry, or `END` when there is none.

This is what makes resume correct. A node that failed leaves a `FAILED` entry
rather than a `COMPLETED` one, so it is selected again on the next run while every
completed node stays untouched. The full transition table for later batches is
kept in `PLANNED_EDGES` as the reference when those nodes land.

## 2. Checkpoint and resume

`app/agents/graph/checkpoint.py` is the seam with LangGraph's checkpointer.

* The thread identity is always the investigation id
  (`investigation_thread_id()`), so resume is keyed by the same id the rest of the
  system uses.
* `InMemoryCheckpointStore` wraps LangGraph's `InMemorySaver`. It is **process-local
  only** — state is lost on restart. It exists so resume is fully exercisable now.
  It is not database persistence.
* `build_checkpoint_store("postgres")` raises
  `UnsupportedCheckpointBackendError`. Failing loudly is deliberate: silently
  degrading to memory in production would make investigations look durable when
  they are not.
* The store's msgpack allowlist is derived from `InvestigationState`'s transitive
  schema types rather than written by hand, so the checkpointer accepts only the
  state model and the schemas it references.

`LangGraphInvestigationService.resume_investigation()` clears the previous error,
sets the status back to `RUNNING`, and re-invokes the graph. Completed nodes are
not re-executed — `tests/agents/test_investigation_engine.py` asserts that each
pre-existing node still has exactly one `COMPLETED` entry afterwards.

A failure leaves the investigation `FAILED` with `current_step=FAILURE`, a stored
`InvestigationError` carrying the read layer's message (never a traceback), and
`retry_count` incremented. The failure is represented, not swallowed.

## 3. The service

`LangGraphInvestigationService` implements the frozen Batch 1 `InvestigationService`
boundary. It owns only what must sit outside the graph: the severity policy, the
idempotency key, thread mapping, and translating a graph failure into a stored
`FAILED` state. `InMemoryInvestigationService` from Batch 1 is unchanged and still
used by the boundary contract tests.

### Idempotency

Batch 1 defines the investigation identity as the `investigation_id` UUID and does
not define how a repeated request maps onto an existing investigation. Left
undefined, two deliveries of the same Member 1 fraud result would create two
investigations and two diverging audit trails.

Batch 2's choice is the key `(transaction_id, case_id)`, implemented in
`investigation_identity_key()`. Re-delivering the same fraud result is refused
(`InvestigationAlreadyCompletedError`, or `...AlreadyRunningError` while in
flight); a genuinely different case for the same transaction still gets its own
investigation.

**This is a cross-member decision, not a Batch 1 contract.** Member 1 owns when a
fraud result is emitted and Member 4 owns where the mapping is persisted. Both
should confirm it before it becomes load-bearing.

## 4. Fake read tools

`app/agents/tools/fakes.py` implements the Batch 1 tool protocols with a fixed
dataset, so the engine runs offline and assertions can be exact.

* Gated by `FRAUDOPS_INVESTIGATION_ALLOW_FAKE_TOOLS=true`. The check runs on every
  tool call, so a toolset built while the gate was open stops working once it is
  closed.
* Every payload carries a `FAKE-DATA` reference prefix.
* No randomness and no fraud intelligence: literals plus plain
  `AmountStatistics` arithmetic. It does not score, rank or conclude.
* Row limits are validated and capped so a tool cannot flood the context window.

These are test and local-run adapters. Member 4 provides the real read layer
behind the same unchanged protocols.

## 5. Contract gaps (open requests, not redesigned here)

1. **No dedicated transaction-detail tool.** `InvestigationState.transaction_context`
   is optional. When Member 1 supplies the snapshot, `load_transaction_context`
   uses it and calls nothing. Otherwise it locates the row through
   `get_recent_transactions`, scoped to the known customer or merchant.
   *Request to Member 4: a single-transaction read tool, so the fallback stops
   being a bounded list scan.*

2. **`get_prior_cases` is wired but never called.** The frozen Batch 1
   `InvestigationState` has no field to carry prior cases, and Batch 1 is
   approved. The toolset exposes the tool and the fake implements it, but no node
   calls it rather than inventing a state field.
   *Request: a Batch 1 contract amendment adding a prior-cases field, or an
   explicit decision that prior-case context stays out of the state.*

3. **No approved retry policy.** `InvestigationSettings.max_tool_retries` exists
   from Batch 1. Batch 2 does **not** retry inside a node: a failed read fails the
   investigation, which is resumable. Retrying a read automatically would need a
   decision about which tools are safe to retry and how backoff interacts with
   `InvestigationSettings.investigation_timeout_seconds`.
   *Request: confirm whether automatic in-node retry is wanted before implementing.*

4. **Production persistence.** Owner: Member 4. `InMemoryCheckpointStore` is
   process-local and must not be used in a deployment.

## 6. Batch boundary — what is deliberately absent

* No language model is called. `openai` is not in `requirements.txt`; it arrives
  with the batch that adds narration or recommendation. Nothing in the engine
  constructs a model client.
* No behavioural, business or relationship analysis. `behavioral_findings`,
  `business_findings` and `relationship_findings` stay empty; `related_entities`
  is stored but never interpreted.
* No evidence pack, no `Recommendation`, no `confidence`.
* No `WAITING_HUMAN` transition — human handoff is a later batch.
* No database, migrations, HTTP layer or frontend work.

## 7. Test map

| File | Covers |
| --- | --- |
| `tests/agents/test_workflow.py` | graph assembly, the audit-trail dispatcher, the planned transition table |
| `tests/agents/test_nodes.py` | each node's happy path, resume skip, refusal to invent data |
| `tests/agents/test_checkpoint.py` | thread identity, store contract, refused backends |
| `tests/agents/test_fakes.py` | gate, determinism, arithmetic, scope and limit validation |
| `tests/agents/test_investigation_engine.py` | full run, idempotency, failure, resume |
| `tests/agents/test_investigation_service.py` | the Batch 1 boundary (unchanged) |