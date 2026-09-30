"""Pydantic request/response schemas for the FraudOps backend.

Module map
----------
``investigation``
    Member 1 -> Member 2 contract (what the deterministic risk engine sends to
    the agentic investigation layer) plus the enums shared across modules.
``investigation_result``
    Member 2 -> Member 3 contract (what the reviewer console consumes).

Ownership
---------
Member 2 owns the two investigation modules in this package. Member 1 owns any
transaction/rule/case schemas added here. This ``__init__`` file intentionally
re-exports nothing so that the package can be extended by several members
without merge conflicts; import from the concrete modules instead.
"""
