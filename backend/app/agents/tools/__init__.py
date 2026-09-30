"""Approved investigation tools for the agentic workflow (Member 2).

The agent reaches system data only through these narrow, read-mostly
interfaces -- never arbitrary database access
(``System Design`` addendum, "Agent Tooling").

Batch 1 status
--------------
Every tool module currently contains a ``Protocol`` (the contract) and a stub
whose methods raise :class:`~app.agents.tools.base.ToolNotImplementedError`.
The stubs deliberately raise instead of returning sample data so that no demo
or test can present fabricated fraud evidence as a real finding.

Naming
------
Method names follow ``Agent System Design`` section 7. The functional brief used
the aliases ``get_transaction_history``, ``get_merchant_context`` and
``get_previous_cases``; they map onto ``get_recent_transactions``,
``get_merchant_profile`` and ``get_prior_cases`` respectively. See
``docs/member2/tool-contract.md``.
"""

from __future__ import annotations

from app.agents.tools.base import (
    InvestigationToolError,
    InvestigationToolset,
    ToolCallRecord,
    ToolNotImplementedError,
    ToolStatus,
    tool_reference,
)
from app.agents.tools.case_tools import (
    CaseUpdater,
    CaseWriteResult,
    EvidenceWriter,
    PriorCasesTool,
    PriorCasesToolStub,
)
from app.agents.tools.customer_tools import CustomerHistoryTool, CustomerHistoryToolStub
from app.agents.tools.merchant_tools import MerchantProfileTool, MerchantProfileToolStub
from app.agents.tools.relationship_tools import (
    RelatedEntitiesTool,
    RelatedEntitiesToolStub,
)
from app.agents.tools.transaction_tools import (
    RecentTransactionsTool,
    RecentTransactionsToolStub,
    RuleResultsTool,
    RuleResultsToolStub,
)

__all__ = [
    "CaseUpdater",
    "CaseWriteResult",
    "CustomerHistoryTool",
    "CustomerHistoryToolStub",
    "EvidenceWriter",
    "InvestigationToolError",
    "InvestigationToolset",
    "MerchantProfileTool",
    "MerchantProfileToolStub",
    "PriorCasesTool",
    "PriorCasesToolStub",
    "RecentTransactionsTool",
    "RecentTransactionsToolStub",
    "RelatedEntitiesTool",
    "RelatedEntitiesToolStub",
    "RuleResultsTool",
    "RuleResultsToolStub",
    "ToolCallRecord",
    "ToolNotImplementedError",
    "ToolStatus",
    "tool_reference",
]
