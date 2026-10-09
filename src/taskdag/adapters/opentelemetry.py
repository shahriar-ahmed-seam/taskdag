"""OpenTelemetry and JSONL Trajectory Exporter.

Exports TaskDAG execution states and node lifecycles into industry-standard
OpenTelemetry trace format and JSONL trajectory files.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from taskdag.core.models import ExecutionState, TaskDAG


class OpenTelemetryExporter:
    """Exports execution trace states as OTel spans and JSONL lines."""

    @staticmethod
    def export_spans(dag: TaskDAG, state: ExecutionState) -> List[Dict[str, Any]]:
        """Generate OpenTelemetry-compliant trace span representations."""
        trace_id = f"trace-{state.run_id}"
        spans: List[Dict[str, Any]] = []

        # Root DAG execution span
        root_span = {
            "trace_id": trace_id,
            "span_id": f"span-root-{state.dag_id}",
            "parent_span_id": None,
            "name": f"taskdag.execute:{dag.name}",
            "start_time": state.start_time,
            "end_time": state.end_time or state.start_time,
            "status": {"code": "OK" if state.status == "COMPLETED" else "ERROR"},
            "attributes": {
                "dag.id": dag.id,
                "dag.mode": str(state.mode.value),
                "dag.nodes_count": len(dag.nodes),
                "dag.completed_count": len(state.completed_nodes),
                "dag.failed_count": len(state.failed_nodes),
                "dag.replan_count": len(state.replanning_events),
            },
        }
        spans.append(root_span)

        # Child node spans
        for nid, node in dag.nodes.items():
            node_span = {
                "trace_id": trace_id,
                "span_id": f"span-node-{nid}",
                "parent_span_id": root_span["span_id"],
                "name": f"taskdag.node:{node.title}",
                "status": {"code": "OK" if node.status.value == "COMPLETED" else "ERROR"},
                "attributes": {
                    "node.id": node.id,
                    "node.status": node.status.value,
                    "node.retries": node.retry_count,
                    "node.error": node.error or "",
                },
            }
            spans.append(node_span)

        return spans

    @staticmethod
    def to_jsonl(spans: List[Dict[str, Any]]) -> str:
        """Convert list of spans into newline-delimited JSON string."""
        return "\n".join(json.dumps(s) for s in spans)
