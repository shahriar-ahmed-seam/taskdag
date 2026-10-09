"""Subtask Separability Analyzer.

Enforces Rule 1 from the architectural playbook:
'Decompose tasks by DAG, not job titles.'
'Single agent wins unless subtasks are truly separable.'
Avoids the Unnecessary Coordination Tax when subtasks have tight feedback coupling.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from taskdag.core.models import (
    SubtaskSeparabilityAnalysis,
    TaskDAG,
    TaskNode,
)
from taskdag.core.types import EdgeType, ExecutionMode, NodeStatus


class SeparabilityAnalyzer:
    """Evaluates task separability and decides between monolithic execution and concurrent DAG."""

    def __init__(self, separability_threshold: float = 0.50, alpha: float = 0.70):
        """
        Initialize analyzer.

        Args:
            separability_threshold: Score cutoff above which tasks are split into concurrent DAG nodes.
            alpha: Weight for context overlap vs coupling coefficient.
        """
        self.threshold = separability_threshold
        self.alpha = alpha

    def analyze(
        self,
        task_id: str,
        subtask_specs: List[Dict[str, Any]],
        shared_invariants: Optional[List[str]] = None,
    ) -> SubtaskSeparabilityAnalysis:
        """
        Compute formal separability score S(T) based on read/write state sets and coupling.

        Args:
            task_id: Identifier of the overarching goal.
            subtask_specs: List of dicts, each containing:
                - 'id': str
                - 'title': str
                - 'read_keys': List[str]
                - 'write_keys': List[str]
                - 'interactive_feedback': bool (optional)
            shared_invariants: Global read-only keys that do not count as conflict overlap.

        Returns:
            SubtaskSeparabilityAnalysis with formal score and dispatch recommendation.
        """
        if not subtask_specs:
            return SubtaskSeparabilityAnalysis(
                task_id=task_id,
                subtasks=[],
                read_keys={},
                write_keys={},
                context_overlap_keys=[],
                total_context_keys=[],
                overlap_ratio=0.0,
                separability_score=1.0,
                is_separable=False,
                recommended_mode=ExecutionMode.SINGLE_AGENT_MONOLITH,
                rationale="Empty subtask specification defaults to single-agent monolith.",
            )

        if len(subtask_specs) == 1:
            return SubtaskSeparabilityAnalysis(
                task_id=task_id,
                subtasks=[subtask_specs[0].get("id", "subtask-1")],
                read_keys={subtask_specs[0].get("id", "subtask-1"): subtask_specs[0].get("read_keys", [])},
                write_keys={subtask_specs[0].get("id", "subtask-1"): subtask_specs[0].get("write_keys", [])},
                context_overlap_keys=[],
                total_context_keys=list(set(subtask_specs[0].get("read_keys", []) + subtask_specs[0].get("write_keys", []))),
                overlap_ratio=0.0,
                separability_score=1.0,
                is_separable=False,
                recommended_mode=ExecutionMode.SINGLE_AGENT_MONOLITH,
                rationale="Single subtask is non-decomposed; single-agent execution has zero coordination tax.",
            )

        subtask_ids: List[str] = []
        read_map: Dict[str, List[str]] = {}
        write_map: Dict[str, List[str]] = {}
        all_keys: Set[str] = set()
        shared_readonly = set(shared_invariants or [])

        feedback_coupling_count = 0

        for spec in subtask_specs:
            sid = str(spec.get("id", f"subtask-{len(subtask_ids)+1}"))
            subtask_ids.append(sid)
            r_keys = list(set(spec.get("read_keys", [])))
            w_keys = list(set(spec.get("write_keys", [])))
            read_map[sid] = r_keys
            write_map[sid] = w_keys
            all_keys.update(r_keys)
            all_keys.update(w_keys)
            if spec.get("interactive_feedback", False):
                feedback_coupling_count += 1

        # Identify mutable state overlaps across different subtasks
        overlap_keys: Set[str] = set()
        n = len(subtask_specs)

        for i in range(n):
            sid_i = subtask_ids[i]
            w_i = set(write_map[sid_i]) - shared_readonly
            r_i = set(read_map[sid_i]) - shared_readonly

            for j in range(i + 1, n):
                sid_j = subtask_ids[j]
                w_j = set(write_map[sid_j]) - shared_readonly
                r_j = set(read_map[sid_j]) - shared_readonly

                # RAW / WAR / WAW conflicts indicate mutable context coupling
                conflicts = (w_i & r_j) | (r_i & w_j) | (w_i & w_j)
                overlap_keys.update(conflicts)

        total_keys_count = len(all_keys)
        overlap_ratio = len(overlap_keys) / total_keys_count if total_keys_count > 0 else 0.0

        # Coupling penalty from feedback loops (e.g. interactive REPL / code-test circularity)
        coupling_coefficient = (feedback_coupling_count / n) if n > 0 else 0.0

        # Separability score S(T)
        raw_penalty = (self.alpha * overlap_ratio) + ((1.0 - self.alpha) * coupling_coefficient)
        separability_score = max(0.0, min(1.0, 1.0 - raw_penalty))
        is_separable = separability_score >= self.threshold

        if is_separable:
            recommended_mode = ExecutionMode.DYNAMIC_DAG_CONCURRENT
            rationale = (
                f"Separability score {separability_score:.3f} >= threshold {self.threshold:.2f}. "
                f"Subtasks have low state overlap ({overlap_ratio:.1%}) and can be orchestrated as a concurrent DAG."
            )
        else:
            recommended_mode = ExecutionMode.SINGLE_AGENT_MONOLITH
            rationale = (
                f"Separability score {separability_score:.3f} < threshold {self.threshold:.2f}. "
                f"High shared mutable context ({overlap_ratio:.1%}) or feedback coupling ({coupling_coefficient:.1%}). "
                "Single agent execution recommended to eliminate coordination tax and lossy handoffs."
            )

        return SubtaskSeparabilityAnalysis(
            task_id=task_id,
            subtasks=subtask_ids,
            read_keys=read_map,
            write_keys=write_map,
            context_overlap_keys=sorted(list(overlap_keys)),
            total_context_keys=sorted(list(all_keys)),
            overlap_ratio=round(overlap_ratio, 4),
            separability_score=round(separability_score, 4),
            is_separable=is_separable,
            recommended_mode=recommended_mode,
            rationale=rationale,
        )

    def synthesize_dag(
        self,
        task_id: str,
        name: str,
        subtask_specs: List[Dict[str, Any]],
        description: str = "",
    ) -> TaskDAG:
        """
        Synthesize a validated TaskDAG from subtask specifications with inferred dependency edges.
        """
        analysis = self.analyze(task_id, subtask_specs)

        dag = TaskDAG(
            id=task_id,
            name=name,
            description=description,
            execution_mode=analysis.recommended_mode,
            metadata={"separability_analysis": analysis.model_dump(mode="json")},
        )

        for spec in subtask_specs:
            sid = str(spec.get("id"))
            node = TaskNode(
                id=sid,
                title=spec.get("title", sid),
                description=spec.get("description", ""),
                input_keys=spec.get("read_keys", []),
                output_keys=spec.get("write_keys", []),
                preconditions=spec.get("preconditions", []),
                postconditions=spec.get("postconditions", []),
                status=NodeStatus.PENDING,
                metadata=spec.get("metadata", {}),
            )
            dag.add_node(node)

        # Infer dependency edges based on producer-consumer dataflow
        for i, consumer_spec in enumerate(subtask_specs):
            c_id = str(consumer_spec.get("id"))
            c_reads = set(consumer_spec.get("read_keys", []))

            explicit_deps = consumer_spec.get("depends_on", [])
            for dep in explicit_deps:
                if dep in dag.nodes:
                    dag.add_edge(dep, c_id, edge_type=EdgeType.DEPENDS_ON)

            # Data flow edges: if earlier node produced a key this node consumes
            for j in range(i):
                producer_spec = subtask_specs[j]
                p_id = str(producer_spec.get("id"))
                p_writes = set(producer_spec.get("write_keys", []))
                common_data = c_reads & p_writes
                if common_data and not any(e.source == p_id and e.target == c_id for e in dag.edges):
                    dag.add_edge(
                        source=p_id,
                        target=c_id,
                        edge_type=EdgeType.DATA_FLOW,
                        passed_data_keys=sorted(list(common_data)),
                    )

        dag.detect_cycles()
        return dag
