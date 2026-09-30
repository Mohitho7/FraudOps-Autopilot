"""Investigation graph package (Member 2): state, nodes and workflow assembly."""

from __future__ import annotations

from app.agents.graph.checkpoint import (
    InMemoryCheckpointStore,
    InvestigationCheckpointStore,
    build_checkpoint_store,
    investigation_thread_id,
)
from app.agents.graph.errors import (
    CheckpointError,
    InvestigationWorkflowError,
    ToolExecutionError,
    UnsupportedCheckpointBackendError,
)
from app.agents.graph.nodes import (
    ANALYSIS_STEPS,
    CONTEXT_LOADING_NODES,
    INVESTIGATION_NODE_SEQUENCE,
    NODE_DESCRIPTIONS,
    TERMINAL_STEPS,
    TERMINATE_INVESTIGATION,
    FinalizeInvestigationNode,
    InitializeInvestigationNode,
    InvestigationNode,
    LoadCustomerContextNode,
    LoadMerchantContextNode,
    LoadRelationshipContextNode,
    LoadTransactionContextNode,
    ValidateInvestigationInputNode,
    node_completed,
)
from app.agents.graph.state import STATE_SCHEMA_VERSION, InvestigationState
from app.agents.graph.workflow import (
    BATCH2_NODE_CLASSES,
    BATCH2_NODE_NAMES,
    PLANNED_EDGES,
    build_batch2_nodes,
    build_investigation_graph,
    route_next_node,
)

__all__ = [
    "ANALYSIS_STEPS",
    "BATCH2_NODE_CLASSES",
    "BATCH2_NODE_NAMES",
    "CONTEXT_LOADING_NODES",
    "INVESTIGATION_NODE_SEQUENCE",
    "NODE_DESCRIPTIONS",
    "PLANNED_EDGES",
    "STATE_SCHEMA_VERSION",
    "TERMINAL_STEPS",
    "TERMINATE_INVESTIGATION",
    "CheckpointError",
    "FinalizeInvestigationNode",
    "InMemoryCheckpointStore",
    "InitializeInvestigationNode",
    "InvestigationCheckpointStore",
    "InvestigationNode",
    "InvestigationState",
    "InvestigationWorkflowError",
    "LoadCustomerContextNode",
    "LoadMerchantContextNode",
    "LoadRelationshipContextNode",
    "LoadTransactionContextNode",
    "ToolExecutionError",
    "UnsupportedCheckpointBackendError",
    "ValidateInvestigationInputNode",
    "build_batch2_nodes",
    "build_checkpoint_store",
    "build_investigation_graph",
    "investigation_thread_id",
    "node_completed",
    "route_next_node",
]