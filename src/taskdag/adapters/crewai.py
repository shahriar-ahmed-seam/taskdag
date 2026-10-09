"""CrewAI Ecosystem Adapter.

Converts static role-based pipelines (CrewAI agents and tasks) into TaskDAG
format, stripping away artificial persona constraints and measuring the coordination tax.
"""

from __future__ import annotations

from typing import Any, Dict

from taskdag.core.models import TaskDAG, TaskNode
from taskdag.core.types import EdgeType, ExecutionMode


class CrewAIAdapter:
    """Converts CrewAI role/task arrays into dynamic TaskDAG."""

    @staticmethod
    def to_taskdag(crew_spec: Dict[str, Any], dag_id: str = "crewai-import") -> TaskDAG:
        """
        Convert CrewAI crew specification to TaskDAG.

        Expected schema:
            tasks: List[Dict[str, Any]] (description, agent, expected_output)
            process: 'sequential' | 'hierarchical'
        """
        dag = TaskDAG(
            id=dag_id,
            name=crew_spec.get("name", "CrewAI Decomposed Workflow"),
            description=crew_spec.get("description", "Converted from CrewAI sequential/hierarchical team"),
            execution_mode=ExecutionMode.DYNAMIC_DAG_CONCURRENT,
            metadata={"source": "crewai", "original_process": crew_spec.get("process", "sequential")},
        )

        tasks = crew_spec.get("tasks", [])
        prev_node_id: str | None = None

        for idx, t in enumerate(tasks):
            node_id = t.get("id", f"task_{idx+1}")
            role = t.get("agent", {}).get("role", "Worker") if isinstance(t.get("agent"), dict) else str(t.get("agent", "Worker"))
            title = f"{role}: {t.get('description', node_id)[:30]}"

            node = TaskNode(
                id=node_id,
                title=title,
                description=t.get("description", ""),
                input_keys=t.get("input_keys", []),
                output_keys=t.get("output_keys", ["result"]),
                metadata={"original_role": role},
            )
            dag.add_node(node)

            # In sequential process, chain nodes
            if crew_spec.get("process", "sequential") == "sequential":
                if prev_node_id is not None:
                    dag.add_edge(prev_node_id, node_id, edge_type=EdgeType.DEPENDS_ON)
                prev_node_id = node_id

        dag.detect_cycles()
        return dag
