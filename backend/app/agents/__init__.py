"""Agentic investigation package (Member 2).

Responsibility
--------------
Member 2 owns everything under this package: investigation orchestration,
investigation state, behavioral analysis, business/merchant context analysis,
relationship analysis, evidence building, recommendation, the agent activity
audit trail and human handoff.

This package does **not** contain fraud rules, risk scoring, velocity checks or
impossible-travel calculations. Those stay in Member 1's rule engine, which
remains the source of truth for deterministic fraud detection
(``Agent System Design`` sections 2 and 9).

Sub-packages
------------
``config``
    Environment-driven settings for the investigation layer.
``graph``
    LangGraph workflow skeleton and the investigation state.
``behavioral`` / ``business`` / ``relationship``
    The three investigation capabilities.
``evidence``
    Evidence pack assembly.
``recommendation``
    Advisory recommendation capability.
``tools``
    Approved, least-privilege tool interfaces the workflow may call.
``prompts``
    Prompt templates for narration only (no deterministic calculations).
"""

__all__: list[str] = []
