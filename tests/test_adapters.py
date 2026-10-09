"""Unit tests for ecosystem adapters (LangGraph, CrewAI, OpenTelemetry)."""

from taskdag.adapters.crewai import CrewAIAdapter
from taskdag.adapters.langgraph import LangGraphAdapter
from taskdag.adapters.opentelemetry import OpenTelemetryExporter
from taskdag.core.models import ExecutionState, TaskDAG, TaskNode


def test_langgraph_adapter_roundtrip():
    spec = {
        "name": "StateGraph Compiler",
        "nodes": {
            "fetch": {"title": "Fetch Webpage", "output_keys": ["html"]},
            "parse": {"title": "Parse HTML", "input_keys": ["html"], "output_keys": ["text"]},
        },
        "edges": [{"source": "fetch", "target": "parse"}],
    }

    dag = LangGraphAdapter.to_taskdag(spec, dag_id="lg-1")
    assert len(dag.nodes) == 2
    assert len(dag.edges) == 1
    assert dag.topological_sort() == ["fetch", "parse"]

    exported = LangGraphAdapter.from_taskdag(dag)
    assert exported["name"] == "StateGraph Compiler"
    assert "fetch" in exported["nodes"]
    assert len(exported["edges"]) == 1


def test_crewai_adapter_conversion():
    crew_spec = {
        "name": "Research Crew",
        "process": "sequential",
        "tasks": [
            {"id": "t1", "description": "Search arXiv papers", "agent": {"role": "Researcher"}},
            {"id": "t2", "description": "Write technical report", "agent": {"role": "Writer"}},
        ],
    }

    dag = CrewAIAdapter.to_taskdag(crew_spec, dag_id="crew-1")
    assert len(dag.nodes) == 2
    assert len(dag.edges) == 1
    assert "t1" in dag.nodes
    assert "t2" in dag.nodes
    assert dag.topological_sort() == ["t1", "t2"]


def test_opentelemetry_export():
    dag = TaskDAG(id="otel-dag", name="OTel Telemetry Run")
    dag.add_node(TaskNode(id="n1", title="Node 1"))
    state = ExecutionState(
        run_id="run-100",
        dag_id="otel-dag",
        status="COMPLETED",
        start_time=100.0,
        end_time=102.5,
        completed_nodes=["n1"],
    )

    spans = OpenTelemetryExporter.export_spans(dag, state)
    assert len(spans) == 2  # 1 root span + 1 node span
    assert spans[0]["name"] == "taskdag.execute:OTel Telemetry Run"
    assert spans[0]["attributes"]["dag.id"] == "otel-dag"

    jsonl = OpenTelemetryExporter.to_jsonl(spans)
    assert "taskdag.execute" in jsonl
    assert "span-node-n1" in jsonl
