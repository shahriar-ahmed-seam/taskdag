"""Bidirectional LangGraph Ecosystem Adapter.

Enables bidirectional conversion between LangGraph StateGraph specifications
and TaskDAG per-task DAG format with dynamic replanning support.
"""

from __future__ import annotations

from typing import Any, Dict, List

from taskdag.core.models import TaskDAG, TaskNode
from taskdag.core.types import EdgeType, ExecutionMode


class LangGraphAdapter:
    """Converts between LangGraph state dictionaries and TaskDAG instances."""

    @staticmethod
    def to_taskdag(langgraph_spec: Dict[str, Any], dag_id: str = "langgraph-import") -> TaskDAG:
        """
        Convert a LangGraph definition dictionary to a TaskDAG.

        Expected schema:
            nodes: Dict[str, Dict[str, Any]]
            edges: List[Dict[str, str]] or List[Tuple[str, str]]
        """
        dag = TaskDAG(
            id=dag_id,
            name=langgraph_spec.get("name", "LangGraph Workflow"),
            description=langgraph_spec.get("description", "Imported from LangGraph StateGraph"),
            execution_mode=ExecutionMode.DYNAMIC_DAG_CONCURRENT,
            metadata={"source": "langgraph"},
        )

        raw_nodes = langgraph_spec.get("nodes", {})
        if isinstance(raw_nodes, dict):
            for node_id, node_spec in raw_nodes.items():
                if isinstance(node_spec, dict):
                    node = TaskNode(
                        id=str(node_id),
                        title=node_spec.get("title", str(node_id)),
                        description=node_spec.get("description", ""),
                        input_keys=node_spec.get("input_keys", []),
                        output_keys=node_spec.get("output_keys", []),
                        metadata=node_spec.get("metadata", {}),
                    )
                else:
                    node = TaskNode(id=str(node_id), title=str(node_id))
                dag.add_node(node)
        elif isinstance(raw_nodes, list):
            for item in raw_nodes:
                nid = item if isinstance(item, str) else item.get("id")
                dag.add_node(TaskNode(id=str(nid), title=str(nid)))

        raw_edges = langgraph_spec.get("edges", [])
        for e in raw_edges:
            if isinstance(e, dict):
                src = e["source"]
                tgt = e["target"]
                dag.add_edge(src, tgt, edge_type=EdgeType.DEPENDS_ON)
            elif isinstance(e, (list, tuple)) and len(e) >= 2:
                dag.add_edge(str(e[0]), str(e[1]), edge_type=EdgeType.DEPENDS_ON)

        dag.detect_cycles()
        return dag

    @staticmethod
    def from_taskdag(dag: TaskDAG) -> Dict[str, Any]:
        """Convert a TaskDAG instance to LangGraph StateGraph specification."""
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        for nid, node in dag.nodes.items():
            nodes_dict[nid] = {
                "id": node.id,
                "title": node.title,
                "input_keys": node.input_keys,
                "output_keys": node.output_keys,
                "status": node.status.value,
            }

        edges_list: List[Dict[str, str]] = [
            {"source": e.source, "target": e.target, "edge_type": e.edge_type.value}
            for e in dag.edges
        ]

        return {
            "name": dag.name,
            "id": dag.id,
            "nodes": nodes_dict,
            "edges": edges_list,
            "entry_point": dag.topological_sort()[0] if dag.nodes else None,
            "metadata": dag.metadata,
        }
