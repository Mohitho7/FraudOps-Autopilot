"""Investigation workflow nodes (Member 2).

The node vocabulary and order follow ``Agent System Design`` section 8::

    START -> Load State -> Check Evidence
      |- sufficient  -> Build Evidence
      |- insufficient-> Select Next Check
                        -> Call Approved Tool -> Validate Output
                        -> Persist Finding / Evidence
                        -> Re-evaluate Evidence
    Build Evidence -> Recommendation -> Human Handoff -> END

Batch 2 status
--------------
This module originally defined only the node vocabulary. Batch 2 implements the
first six nodes of the workflow on top of that vocabulary; the analysis,
evidence, recommendation and handoff nodes stay declarative until their batch.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol

from langgraph.graph import END

from app.agents.graph.errors import ToolExecutionError
from app.agents.graph.state import InvestigationState
from app.agents.tools.base import ToolCallRecord, ToolStatus
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationStep,
    TransactionContext,
    TransactionStatus,
)
from app.schemas.investigation_result import InvestigationActivity, InvestigationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.agents.tools.base import InvestigationToolset

__all__ = [
    "ANALYSIS_STEPS",
    "CONTEXT_LOADING_NODES",
    "INVESTIGATION_NODE_SEQUENCE",
    "NODE_DESCRIPTIONS",
    "TERMINAL_STEPS",
    "TERMINATE_INVESTIGATION",
    "FinalizeInvestigationNode",
    "InitializeInvestigationNode",
    "InvestigationNode",
    "LoadCustomerContextNode",
    "LoadMerchantContextNode",
    "LoadRelationshipContextNode",
    "LoadTransactionContextNode",
    "ValidateInvestigationInputNode",
    "node_completed",
]

TERMINATE_INVESTIGATION = END
"""Router sentinel meaning "nothing left to do; end the graph".

It is LangGraph's own ``END`` so the router can return it directly instead of
routing through an extra node.
"""

INVESTIGATION_NODE_SEQUENCE: tuple[InvestigationStep, ...] = (
    InvestigationStep.LOAD_STATE,
    InvestigationStep.CHECK_EVIDENCE,
    InvestigationStep.SELECT_NEXT_CHECK,
    InvestigationStep.CALL_TOOL,
    InvestigationStep.VALIDATE_OUTPUT,
    InvestigationStep.PERSIST_FINDING,
    InvestigationStep.BEHAVIORAL_ANALYSIS,
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS,
    InvestigationStep.RELATIONSHIP_ANALYSIS,
    InvestigationStep.EVIDENCE_BUILD,
    InvestigationStep.RECOMMENDATION,
    InvestigationStep.HUMAN_HANDOFF,
    InvestigationStep.COMPLETE,
)

ANALYSIS_STEPS: tuple[InvestigationStep, ...] = (
    InvestigationStep.BEHAVIORAL_ANALYSIS,
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS,
    InvestigationStep.RELATIONSHIP_ANALYSIS,
)

TERMINAL_STEPS: tuple[InvestigationStep, ...] = (
    InvestigationStep.COMPLETE,
    InvestigationStep.HUMAN_HANDOFF,
    InvestigationStep.FAILURE,
)

NODE_DESCRIPTIONS: dict[InvestigationStep, str] = {
    InvestigationStep.LOAD_STATE: (
        "Load the persisted investigation state and Member 1's fraud facts."
    ),
    InvestigationStep.CHECK_EVIDENCE: (
        "Decide whether the collected evidence is sufficient to form a case."
    ),
    InvestigationStep.SELECT_NEXT_CHECK: (
        "Choose which investigation capability or tool runs next."
    ),
    InvestigationStep.CALL_TOOL: (
        "Call one approved tool with explicit input identifiers."
    ),
    InvestigationStep.VALIDATE_OUTPUT: (
        "Validate the tool output against its contract before using it."
    ),
    InvestigationStep.PERSIST_FINDING: (
        "Store the finding and its evidence reference, then re-evaluate."
    ),
    InvestigationStep.BEHAVIORAL_ANALYSIS: (
        "Compare the transaction with the customer baseline."
    ),
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS: (
        "Compare the transaction with the merchant business profile."
    ),
    InvestigationStep.RELATIONSHIP_ANALYSIS: (
        "Assess links to other customers, devices, IPs and merchants."
    ),
    InvestigationStep.EVIDENCE_BUILD: (
        "Assemble the structured evidence pack and the analyst summary."
    ),
    InvestigationStep.RECOMMENDATION: (
        "Produce an advisory action: ALLOW, MONITOR, HOLD_FOR_REVIEW or ESCALATE."
    ),
    InvestigationStep.HUMAN_HANDOFF: (
        "Set the case to WAITING_HUMAN and surface it to the reviewer console."
    ),
    InvestigationStep.COMPLETE: "Finalise the investigation and persist the timeline.",
    InvestigationStep.FAILURE: "Record the failure and stop without claiming success.",
}


class InvestigationNode(Protocol):
    """A single LangGraph node.

    Nodes take the current state and return a partial state update. They must
    be side-effect free apart from the tools they call, must record their
    activity in the state timeline, and must never raise past the graph
    boundary without recording an :class:`InvestigationError`
    (``Agent System Design`` section 13).
    """

    step: InvestigationStep

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        """Run the node and return the state fields it updates."""
        ...


# ---------------------------------------------------------------------------
# Batch 2 node implementations
# ---------------------------------------------------------------------------
#
# Node ordering and completion are driven by the investigation's own audit
# trail. Each node records a ``COMPLETED`` activity entry carrying its name in
# ``tool_name``, and a node is considered done when such an entry exists. That
# makes every node idempotent (``Agent System Design`` section 13: "``current_step``
# + ``completed_steps`` make each step idempotent, so a retried investigation
# does not repeat completed work") without adding a field to the frozen
# ``InvestigationState`` schema.
#
# The tool-loading nodes all map onto ``InvestigationStep.CALL_TOOL``, because
# that is what they are. Their identity comes from the activity entry, not from
# the step enum, which is why this module never invents new step values.

CONTEXT_LOADING_NODES: tuple[str, ...] = (
    "load_transaction_context",
    "load_customer_context",
    "load_merchant_context",
    "load_relationship_context",
)
"""Nodes that load stored context through an approved read tool."""


def node_completed(state: InvestigationState, node_name: str) -> bool:
    """Return whether ``node_name`` already finished successfully.

    The check is the audit trail: an entry with ``status=COMPLETED`` and this
    node's name. A node that failed leaves a ``FAILED`` entry instead, so it is
    correctly *not* considered done and a resume retries it.
    """

    return any(
        event.tool_name == node_name and event.status == ToolStatus.COMPLETED
        for event in state.activity
    )


class _BaseNode:
    """Shared bookkeeping for the Batch 2 nodes.

    Handles the three things every node must get right: an idempotency guard,
    audit-trail recording on both success and failure, and building the state
    update LangGraph merges back in.
    """

    step: InvestigationStep = InvestigationStep.LOAD_STATE

    def __init__(self, toolset: InvestigationToolset) -> None:
        self.toolset = toolset

    @property
    def name(self) -> str:
        """Activity name of this node, used for idempotency and audit."""

        raise NotImplementedError

    def _skip(self, state: InvestigationState) -> bool:
        return node_completed(state, self.name)

    def _record(
        self,
        state: InvestigationState,
        *,
        status: str,
        summary: str,
        error: str | None = None,
        step: InvestigationStep | None = None,
    ) -> InvestigationActivity:
        event = state.record_activity(
            step=step or self.step,
            status=status,
            summary=summary,
            tool_name=self.name,
            error=error,
        )
        return event

    def _fail(
        self,
        state: InvestigationState,
        exc: BaseException,
        *,
        summary: str,
        step: InvestigationStep | None = None,
    ) -> dict[str, object]:
        """Record a node failure and build the state update.

        The state is updated *before* the exception propagates, so the failure,
        the activity entry and the attempt counter are part of the checkpoint
        that resume continues from.
        """

        message = str(exc)
        event = self._record(
            state,
            status=ToolStatus.FAILED,
            summary=summary,
            error=message,
            step=step,
        )
        state.error = InvestigationError(
            step=step or self.step,
            error_type=type(exc).__name__,
            message=message,
            retryable=True,
        )
        state.status = InvestigationStatus.FAILED
        state.retry_count += 1
        state.last_checkpoint_at = event.occurred_at
        return {
            "status": state.status,
            "error": state.error,
            "retry_count": state.retry_count,
            "activity": list(state.activity),
            "updated_at": state.updated_at,
            "last_checkpoint_at": state.last_checkpoint_at,
        }

    def _done(
        self,
        state: InvestigationState,
        *,
        summary: str,
        extra: dict[str, object] | None = None,
        step: InvestigationStep | None = None,
    ) -> dict[str, object]:
        """Record success, mark the step done and build the state update."""

        used_step = step or self.step
        event = self._record(
            state,
            status=ToolStatus.COMPLETED,
            summary=summary,
            step=used_step,
        )
        state.mark_step_completed(used_step)
        state.last_checkpoint_at = event.occurred_at
        update: dict[str, object] = {
            "current_step": used_step,
            "completed_steps": list(state.completed_steps),
            "activity": list(state.activity),
            "updated_at": state.updated_at,
            "last_checkpoint_at": state.last_checkpoint_at,
        }
        for field_name, value in (extra or {}).items():
            # Applied to the live state as well as returned, so a node called
            # directly (tests, the failure path) leaves a consistent object.
            # LangGraph merges the returned update on top of the same values.
            setattr(state, field_name, value)
            update[field_name] = value
        return update

    async def _call_tool(
        self,
        tool_name: str,
        input_refs: tuple[str, ...],
        call: Callable[[], Awaitable[Any]],
    ) -> tuple[Any, ToolCallRecord, Any]:
        """Run an approved tool with a recorded call envelope.

        Mirrors the audit requirement in ``docs/member2/tool-contract.md``
        section 4: a ``ToolCallRecord`` is opened before the call, and a failure
        is wrapped in :class:`ToolExecutionError` so the caller records it
        against the investigation.

        Returns:
            The tool's result, the call record, and its ``reference`` if it has
            one.

        Raises:
            ToolExecutionError: When the tool fails. The original exception is
                chained, so the read layer's message survives.
        """

        record = ToolCallRecord.started(
            tool_name=tool_name,
            step=self.step,
            input_refs=input_refs,
        )
        try:
            result = await call()
        except Exception as exc:  # noqa: BLE001 - re-raised as ToolExecutionError
            raise ToolExecutionError(
                f"{tool_name} failed: {exc}",
                step=self.step,
                tool_name=tool_name,
            ) from exc
        record_references = getattr(result, "reference", None)
        return result, record, record_references


class InitializeInvestigationNode(_BaseNode):
    """Prepare the investigation for execution.

    Records the starting audit entry and positions the state at ``LOAD_STATE``.
    It performs no tool call and no analysis.

    ``InvestigationState.transaction_id`` is a required field, so by the time a
    node runs there is always a transaction to investigate. This node therefore
    only asserts what the type system cannot: that the state carries the fields
    the workflow will read.
    """

    step = InvestigationStep.LOAD_STATE

    @property
    def name(self) -> str:
        return "initialize_investigation"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        if state.case_id is None:
            raise ToolExecutionError(
                "investigation has no case id, so it cannot be traced back to "
                "Member 1's fraud result",
                step=self.step,
            )
        state.status = InvestigationStatus.RUNNING
        state.current_step = InvestigationStep.LOAD_STATE
        return self._done(
            state,
            summary=(
                f"Investigation initialised for transaction {state.transaction_id} "
                f"at severity {state.severity} with risk score {state.risk_score} "
                "from the deterministic engine"
            ),
            extra={
                "status": state.status,
                "current_step": state.current_step,
            },
        )


class ValidateInvestigationInputNode(_BaseNode):
    """Confirm the transaction exists and Member 1's rule results are readable.

    This is the Batch 1 ``VALIDATE_OUTPUT`` step used for input validation:
    ``get_rule_results`` is the one tool that is scoped by ``transaction_id``
    alone, so it answers both "does this transaction exist?" and "do the stored
    rule results agree with what Member 1 handed us?".

    Agreement is not enforced. A divergence is recorded as an activity note so
    it surfaces in the audit trail, but the investigation continues with the
    values Member 1 supplied, because Member 1 remains the source of truth for
    deterministic detection.
    """

    step = InvestigationStep.VALIDATE_OUTPUT

    @property
    def name(self) -> str:
        return "validate_investigation_input"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        transaction_id = state.transaction_id
        result, _, reference = await self._call_tool(
            "get_rule_results",
            (f"transaction:{transaction_id}",),
            lambda: self.toolset.rule_results_tool.get_rule_results(transaction_id),
        )
        stored_triggered = sorted(item.rule_id for item in result.triggered)
        supplied_triggered = sorted(item.rule_id for item in state.triggered_rules)
        mismatch = stored_triggered != supplied_triggered
        summary = (
            f"Validated transaction {transaction_id} against {len(result.results)} "
            f"stored rule result(s); {len(stored_triggered)} stored rule(s) "
            f"triggered and {len(supplied_triggered)} supplied by Member 1 "
            "confirmed the same transaction"
        )
        if mismatch:
            summary += (
                f"; triggered rule ids differ (stored {stored_triggered}, supplied "
                f"{supplied_triggered}) - Member 1 remains authoritative"
            )
        summary += f" [source: {reference}]"
        return self._done(state, summary=summary)


class LoadTransactionContextNode(_BaseNode):
    """Load the transaction snapshot the investigation is about.

    Uses the request's snapshot when Member 1 supplied one, otherwise locates
    the transaction through ``get_recent_transactions`` -- an already-approved
    Batch 1 tool scoped to a single subject. No new read interface is introduced
    for this; see ``docs/member2/agent-workflow.md`` for the open request to
    Member 4.
    """

    step = InvestigationStep.CALL_TOOL

    @property
    def name(self) -> str:
        return "load_transaction_context"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        context = state.transaction_context
        if context is not None:
            return self._done(
                state,
                summary=(
                    f"Loaded transaction {context.transaction_id} from the snapshot "
                    "Member 1 supplied on the request; no read tool was needed"
                ),
                extra={"transaction_context": context},
            )

        scope_customer = state.customer_id
        scope_merchant = None if scope_customer is not None else state.merchant_id
        if scope_customer is None and scope_merchant is None:
            raise ToolExecutionError(
                "cannot load the transaction: neither customer_id nor merchant_id "
                "is known, so no approved read tool can be scoped",
                step=self.step,
            )
        scope_ref = (
            f"customer:{scope_customer}"
            if scope_customer is not None
            else f"merchant:{scope_merchant}"
        )
        result, _, _ = await self._call_tool(
            "get_recent_transactions",
            (scope_ref,),
            lambda: self.toolset.transaction_history_tool.get_recent_transactions(
                customer_id=scope_customer,
                merchant_id=scope_merchant,
            ),
        )
        for summary_row in result.transactions:
            if summary_row.transaction_id == state.transaction_id:
                context = TransactionContext(
                    transaction_id=summary_row.transaction_id,
                    customer_id=summary_row.customer_id,
                    merchant_id=summary_row.merchant_id,
                    amount=summary_row.amount,
                    currency=summary_row.currency,
                    timestamp=summary_row.timestamp,
                    latitude=summary_row.latitude,
                    longitude=summary_row.longitude,
                    country=summary_row.country,
                    ip_address=summary_row.ip_address,
                    device_id=summary_row.device_id,
                    status=TransactionStatus.FLAGGED,
                )
                return self._done(
                    state,
                    summary=(
                        f"Loaded transaction {state.transaction_id} from the stored "
                        "transaction history"
                    ),
                    extra={
                        "transaction_context": context,
                        "customer_id": context.customer_id,
                        "merchant_id": context.merchant_id,
                    },
                )
        raise ToolExecutionError(
            f"transaction {state.transaction_id} not found in the stored history "
            "for the known customer or merchant scope",
            step=self.step,
        )


class LoadCustomerContextNode(_BaseNode):
    """Load the customer profile and baseline through the approved tool."""

    step = InvestigationStep.CALL_TOOL

    @property
    def name(self) -> str:
        return "load_customer_context"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        customer_id = state.customer_id
        if customer_id is None:
            raise ToolExecutionError(
                "cannot load customer context: customer_id is unknown",
                step=self.step,
            )
        history, _, reference = await self._call_tool(
            "get_customer_history",
            (f"customer:{customer_id}",),
            lambda: self.toolset.customer_history_tool.get_customer_history(customer_id),
        )
        context = history.context
        summary = (
            f"Loaded customer {customer_id} context: "
            f"{context.transaction_count} transaction(s) in the analysed window"
        )
        if context.amount_statistics is None or not context.amount_statistics.has_baseline:
            summary += "; no amount baseline available"
        summary += f" [source: {reference}]"
        return self._done(
            state,
            summary=summary,
            extra={
                "customer_context": context,
                "customer_id": history.customer_id,
            },
        )


class LoadMerchantContextNode(_BaseNode):
    """Load the merchant business profile through the approved tool."""

    step = InvestigationStep.CALL_TOOL

    @property
    def name(self) -> str:
        return "load_merchant_context"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        merchant_id = state.merchant_id
        if merchant_id is None:
            raise ToolExecutionError(
                "cannot load merchant context: merchant_id is unknown",
                step=self.step,
            )
        context, _, reference = await self._call_tool(
            "get_merchant_profile",
            (f"merchant:{merchant_id}",),
            lambda: self.toolset.merchant_profile_tool.get_merchant_profile(merchant_id),
        )
        summary = (
            f"Loaded merchant {merchant_id} profile: category {context.category}"
        )
        if context.expected_p95 is not None:
            summary += f", expected p95 {context.expected_p95}"
        else:
            summary += ", no expected percentile bands configured"
        summary += f" [source: {reference}]"
        return self._done(
            state,
            summary=summary,
            extra={"merchant_context": context, "merchant_id": context.merchant_id},
        )


class LoadRelationshipContextNode(_BaseNode):
    """Load entities linked to the transaction through the approved tool.

    Batch 2 only *stores* the links on the state. It does not interpret them:
    ranking links or scoring a network is Batch 3 relationship intelligence.
    """

    step = InvestigationStep.CALL_TOOL

    @property
    def name(self) -> str:
        return "load_relationship_context"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        transaction_id = state.transaction_id
        entities, _, _ = await self._call_tool(
            "get_related_entities",
            (f"transaction:{transaction_id}",),
            lambda: self.toolset.relationship_tool.get_related_entities(transaction_id),
        )
        return self._done(
            state,
            summary=(
                f"Loaded {len(entities)} related entity/entities for transaction "
                f"{transaction_id}"
            ),
            extra={"related_entities": list(entities)},
        )


class FinalizeInvestigationNode(_BaseNode):
    """Close the Batch 2 investigation.

    Batch 2 stops here. Evidence synthesis, the recommendation agent and human
    handoff belong to later batches, so the status is ``COMPLETED`` and no
    ``recommendation`` is set: the console receives the deterministic context
    that was loaded and nothing that pretends to be a conclusion.
    """

    step = InvestigationStep.COMPLETE

    @property
    def name(self) -> str:
        return "finalize_investigation"

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        if self._skip(state):
            return {}
        state.status = InvestigationStatus.COMPLETED
        state.current_step = InvestigationStep.COMPLETE
        state.completed_at = state.updated_at
        return self._done(
            state,
            summary=(
                "Investigation context loading completed; evidence synthesis and "
                "recommendation are not part of this batch"
            ),
            extra={
                "status": state.status,
                "current_step": state.current_step,
                "completed_at": state.completed_at,
            },
        )
