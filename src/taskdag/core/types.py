"""Canonical types and enumerations for TaskDAG."""

from enum import Enum


class NodeStatus(str, Enum):
    """Lifecycle state of an individual task node in the DAG."""
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REPLANNED = "REPLANNED"
    SKIPPED = "SKIPPED"
    PRUNED = "PRUNED"


class EdgeType(str, Enum):
    """Semantic coupling between task nodes."""
    DEPENDS_ON = "DEPENDS_ON"
    DATA_FLOW = "DATA_FLOW"
    CONDITIONAL_BRANCH = "CONDITIONAL_BRANCH"
    REMEDIATION = "REMEDIATION"


class ExecutionMode(str, Enum):
    """Execution strategy chosen based on subtask separability analysis."""
    SINGLE_AGENT_MONOLITH = "SINGLE_AGENT_MONOLITH"
    DYNAMIC_DAG_CONCURRENT = "DYNAMIC_DAG_CONCURRENT"


class ReplanActionType(str, Enum):
    """DAG mutation actions executed by the dynamic replanner."""
    SPLIT_NODE = "SPLIT_NODE"
    INJECT_REMEDIATION = "INJECT_REMEDIATION"
    REROUTE_DEPENDENCY = "REROUTE_DEPENDENCY"
    PRUNE_SUBTREE = "PRUNE_SUBTREE"
    DEGRADE_TO_MONOLITH = "DEGRADE_TO_MONOLITH"
