"""Backend service layer.

Member 1 owns the transaction, context, risk, case and notification services
(Backend Specification, section 3). Member 2 owns
:mod:`app.services.investigation_service`, which owns investigation
orchestration entry points. This ``__init__`` file intentionally re-exports
nothing to keep the package merge-friendly across members.
"""
