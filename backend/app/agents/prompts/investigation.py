"""Prompt templates for the investigation layer (Member 2).

These are narration prompts only. They are plain :class:`string.Template`
constants: no model client, no network call and no settings lookup happens at
import time.

Guardrails encoded in every template
------------------------------------
* Never recompute a deterministic fraud value. All numbers come from the
  supplied facts.
* Never contradict or override Member 1's ``risk_score``, ``severity`` or rule
  results.
* Never invent evidence, entities or source references.
* Never request or perform irreversible financial actions.
* Separate observed facts from interpretation, and label them as such
  (``Agent System Design`` section 11).

The LLM is not the source of truth for any numerical fraud calculation
(``Agent System Design`` sections 2 and 9).
"""

from __future__ import annotations

from string import Template

__all__ = [
    "BEHAVIORAL_ANALYSIS_PROMPT",
    "BUSINESS_CONTEXT_PROMPT",
    "DETERMINISTIC_SUMMARY_TEMPLATE",
    "EVIDENCE_SYNTHESIS_PROMPT",
    "GUARDRAIL_PREAMBLE",
    "HANDOFF_SUMMARY_PROMPT",
    "RECOMMENDATION_PROMPT",
    "RELATIONSHIP_ANALYSIS_PROMPT",
]

GUARDRAIL_PREAMBLE = """You are a fraud investigation analyst assistant inside FraudOps.

Hard rules:
- The deterministic rule engine (velocity, unusual amount, impossible travel)
  is the source of truth for risk. Never recalculate, adjust or dispute a
  risk score, severity or rule result. Treat every supplied number as given.
- Use only the facts, evidence references and tool outputs provided below.
  Never invent a transaction, entity, metric or source reference.
- Do not ask for, and never claim to have performed, an irreversible financial
  action such as blocking funds or closing an account.
- Keep observed facts, calculated metrics, rule results and your own
  interpretation clearly separated and explicitly labelled.
- If the evidence is contradictory or incomplete, say so instead of guessing.

"""

BEHAVIORAL_ANALYSIS_PROMPT = Template(
    GUARDRAIL_PREAMBLE
    + """Task: describe whether this transaction is abnormal for this customer.

Customer baseline facts:
$customer_facts

Transaction facts:
$transaction_facts

Deterministic metrics already computed by the system:
$metrics

Return findings that:
1. restate each metric as a labelled statement,
2. reference the evidence ids that support them,
3. separate the observation from your interpretation.
"""
)

BUSINESS_CONTEXT_PROMPT = Template(
    GUARDRAIL_PREAMBLE
    + """Task: describe whether this transaction is economically plausible for
this merchant and business category.

Merchant profile facts:
$merchant_facts

Transaction facts:
$transaction_facts

Deterministic metrics already computed by the system:
$metrics

Context matters more than a global threshold: a large amount can be plausible
at a high-ticket merchant and strongly anomalous at a low-ticket merchant.
Explain the comparison using the supplied percentiles only.
"""
)

RELATIONSHIP_ANALYSIS_PROMPT = Template(
    GUARDRAIL_PREAMBLE
    + """Task: describe the significance of the links found for this transaction.

Discovered entity links:
$entity_links

Deterministic relationship counts:
$metrics

A link is a fact; suspiciousness is your interpretation. Label it as such and
never assert fraud as a fact.
"""
)

EVIDENCE_SYNTHESIS_PROMPT = Template(
    GUARDRAIL_PREAMBLE
    + """Task: assemble an evidence pack narrative for a fraud reviewer.

Findings and their evidence references:
$findings

Stored evidence records:
$evidence

Produce a concise analyst summary that:
- opens with what happened,
- lists the strongest evidence items with their source references,
- states the gaps in the evidence,
- makes no recommendation (that is a separate step).
"""
)

RECOMMENDATION_PROMPT = Template(
    GUARDRAIL_PREAMBLE
    + """Task: recommend the next operational action for this case.

Risk severity (from the deterministic engine, do not change it):
$severity

Evidence summary:
$evidence_summary

Allowed actions: ALLOW, MONITOR, HOLD_FOR_REVIEW, ESCALATE.

Return a recommendation with:
- action,
- confidence between 0 and 1,
- rationale that cites the evidence references,
- whether a human decision is required before any action is taken.

If the evidence is insufficient or contradictory, prefer HOLD_FOR_REVIEW or
ESCALATE over a confident action.
"""
)

HANDOFF_SUMMARY_PROMPT = Template(
    GUARDRAIL_PREAMBLE
    + """Task: write the reviewer-facing briefing shown when the case is handed
to a human.

Findings, evidence and recommendation:
$case_payload

Produce a short briefing that separates:
1. what the deterministic engine detected,
2. what the investigation established,
3. what the agent recommends,
4. what the reviewer must decide.
"""
)

DETERMINISTIC_SUMMARY_TEMPLATE = Template(
    """Investigation $investigation_id on transaction $transaction_id
($severity, risk score $risk_score from the deterministic rule engine).

Findings:
$findings

Evidence:
$evidence

Related entities:
$related_entities

Recommendation: $recommendation (confidence $confidence).

Note: this summary was generated deterministically because no language model
was available. Every statement above comes from stored records.
"""
)
