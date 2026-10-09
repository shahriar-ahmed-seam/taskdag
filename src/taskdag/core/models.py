"""Canonical data models and DAG structures for TaskDAG."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from taskdag.core.types import (
    EdgeType,
    ExecutionMode,
    NodeStatus,
    ReplanActionType,
)


class TaskNode(BaseModel):
    """Discrete, typed unit of work in a task DAG."""

    id: str = Field(..., description="Unique node identifier")
    title: str = Field(..., description="Human-readable title")
    description: str = Field("", description="Detailed task specification")
    input_keys: List[str] = Field(default_factory=list, description="Keys consumed from shared context")
    output_keys: List[str] = Field(default_factory=list, description="Keys produced into context")
    preconditions: List[str] = Field(default_factory=list, description="Logical assertions required before execution")
    postconditions: List[str] = Field(default_factory=list, description="Logical assertions verified after execution")
    status: NodeStatus = Field(default=NodeStatus.PENDING, description="Current lifecycle state")
    assigned_agent_id: Optional[str] = Field(None, description="Optional worker/subagent identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata")
    retry_count: int = Field(default=0, ge=0, description="Number of execution attempts")
    max_retries: int = Field(default=2, ge=0, description="Maximum retry limit before replan")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution output payload")
    error: Optional[str] = Field(None, description="Failure traceback or error message")


class TaskEdge(BaseModel):
    """Directed dependency or data channel between two task nodes."""

    source: str = Field(..., description="Upstream node identifier")
    target: str = Field(..., description="Downstream node identifier")
    edge_type: EdgeType = Field(default=EdgeType.DEPENDS_ON, description="Coupling semantics")
    condition: Optional[str] = Field(None, description="Conditional routing expression if applicable")
    passed_data_keys: List[str] = Field(default_factory=list, description="Specific keys forwarded across edge")


class ReplanningEvent(BaseModel):
    """Audit log entry capturing dynamic DAG mutations in response to runtime deviation."""

    event_id: str = Field(..., description="Unique replanning event identifier")
    trigger_node_id: str = Field(..., description="Node that triggered the replan")
    action_type: ReplanActionType = Field(..., description="Mutation operation applied")
    reason: str = Field(..., description="Root cause explanation for the replan")
    nodes_added: List[str] = Field(default_factory=list, description="Identifiers of inserted nodes")
    nodes_removed: List[str] = Field(default_factory=list, description="Identifiers of pruned nodes")
    edges_modified: List[Dict[str, str]] = Field(default_factory=list, description="Modified edge transitions")
    timestamp: float = Field(..., description="Epoch timestamp of replan event")


class SubtaskSeparabilityAnalysis(BaseModel):
    """Mathematical assessment of subtask separability to prevent coordination tax."""

    task_id: str = Field(..., description="Target task objective identifier")
    subtasks: List[str] = Field(default_factory=list, description="Proposed subtask breakdown")
    read_keys: Dict[str, List[str]] = Field(default_factory=dict, description="Read set per subtask")
    write_keys: Dict[str, List[str]] = Field(default_factory=dict, description="Write set per subtask")
    context_overlap_keys: List[str] = Field(default_factory=list, description="Shared mutable keys")
    total_context_keys: List[str] = Field(default_factory=list, description="Universe of context keys")
    overlap_ratio: float = Field(..., ge=0.0, le=1.0, description="|Overlap| / |TotalContext|")
    separability_score: float = Field(..., ge=0.0, le=1.0, description="1 - overlap_ratio")
    is_separable: bool = Field(..., description="True if score >= separability threshold")
    recommended_mode: ExecutionMode = Field(..., description="Recommended dispatch strategy")
    rationale: str = Field(..., description="Formal engineering explanation of decision")


class ExecutionState(BaseModel):
    """Snapshot of overall DAG execution state and memory."""

    run_id: str = Field(..., description="Unique run identifier")
    dag_id: str = Field(..., description="Executed DAG identifier")
    mode: ExecutionMode = Field(default=ExecutionMode.DYNAMIC_DAG_CONCURRENT)
    status: str = Field(default="PENDING", description="Global execution status")
    start_time: float = Field(default=0.0)
    end_time: Optional[float] = Field(None)
    completed_nodes: List[str] = Field(default_factory=list)
    failed_nodes: List[str] = Field(default_factory=list)
    replanning_events: List[ReplanningEvent] = Field(default_factory=list)
    context_store: Dict[str, Any] = Field(default_factory=dict, description="Compacted context state")


class TaskDAG(BaseModel):
    """Directed Acyclic Graph representing task decomposition."""

    id: str = Field(..., description="Unique DAG identifier")
    name: str = Field(..., description="Descriptive workflow name")
    description: str = Field("", description="Detailed workflow objective")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.DYNAMIC_DAG_CONCURRENT)
    nodes: Dict[str, TaskNode] = Field(default_factory=dict, description="Mapping of node ID to node")
    edges: List[TaskEdge] = Field(default_factory=list, description="Directed dependencies")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_integrity(self) -> TaskDAG:
        """Verify edge endpoints and validate absence of cycles."""
        for edge in self.edges:
            if edge.source not in self.nodes:
                raise ValueError(f"Edge source '{edge.source}' does not exist in nodes")
            if edge.target not in self.nodes:
                raise ValueError(f"Edge target '{edge.target}' does not exist in nodes")
        self.detect_cycles()
        return self

    def add_node(self, node: TaskNode) -> None:
        """Add or overwrite a node in the DAG."""
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        """Remove a node and any connected edges."""
        if node_id in self.nodes:
            del self.nodes[node_id]
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType = EdgeType.DEPENDS_ON,
        condition: Optional[str] = None,
        passed_data_keys: Optional[List[str]] = None,
    ) -> None:
        """Add a directed edge between two existing nodes and check acyclicity."""
        if source not in self.nodes:
            raise KeyError(f"Source node '{source}' not in DAG")
        if target not in self.nodes:
            raise KeyError(f"Target node '{target}' not in DAG")

        # Avoid duplicate edges
        for existing in self.edges:
            if existing.source == source and existing.target == target and existing.edge_type == edge_type:
                return

        edge = TaskEdge(
            source=source,
            target=target,
            edge_type=edge_type,
            condition=condition,
            passed_data_keys=passed_data_keys or [],
        )
        self.edges.append(edge)
        self.detect_cycles()

    def remove_edge(self, source: str, target: str) -> None:
        """Remove all edges from source to target."""
        self.edges = [e for e in self.edges if not (e.source == source and e.target == target)]

    def get_predecessors(self, node_id: str) -> List[str]:
        """Return list of node IDs that target node_id."""
        return [e.source for e in self.edges if e.target == node_id]

    def get_successors(self, node_id: str) -> List[str]:
        """Return list of node IDs that node_id points to."""
        return [e.target for e in self.edges if e.source == node_id]

    def detect_cycles(self) -> None:
        """Perform cycle detection via depth-first search cycle check."""
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            adj[e.source].append(e.target)

        visited: Dict[str, int] = {nid: 0 for nid in self.nodes}  # 0: unvisited, 1: visiting, 2: visited

        def dfs(u: str) -> bool:
            visited[u] = 1
            for v in adj.get(u, []):
                if visited[v] == 1:
                    return True  # Back edge detected -> cycle
                if visited[v] == 0:
                    if dfs(v):
                        return True
            visited[u] = 2
            return False

        for nid in self.nodes:
            if visited[nid] == 0:
                if dfs(nid):
                    raise ValueError(f"Cycle detected in TaskDAG '{self.id}' involving node '{nid}'")

    def topological_sort(self) -> List[str]:
        """Return a valid topological ordering of node IDs (Kahn's algorithm)."""
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}

        for e in self.edges:
            adj[e.source].append(e.target)
            in_degree[e.target] = in_degree.get(e.target, 0) + 1

        queue: List[str] = [nid for nid, deg in in_degree.items() if deg == 0]
        order: List[str] = []

        while queue:
            # Deterministic ordering by node id
            queue.sort()
            curr = queue.pop(0)
            order.append(curr)

            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise ValueError(f"TaskDAG '{self.id}' contains a cycle or unreachable nodes in topological sort")

        return order

    def to_json(self, indent: int = 2) -> str:
        """Serialize DAG to JSON string."""
        return json.dumps(self.model_dump(mode="json"), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> TaskDAG:
        """Deserialize DAG from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def to_yaml(self) -> str:
        """Serialize DAG to YAML string."""
        return yaml.dump(self.model_dump(mode="json"), sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> TaskDAG:
        """Deserialize DAG from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(**data)
