"""Unit tests for TaskDAG core structures, topological sorting, and cycle detection."""

import json

import pytest

from taskdag.core.models import TaskDAG, TaskNode
from taskdag.core.types import EdgeType, ExecutionMode


def test_task_dag_creation_and_topology():
    dag = TaskDAG(
        id="dag-test-01",
        name="Compilation Pipeline",
        description="Compile and verify module",
        execution_mode=ExecutionMode.DYNAMIC_DAG_CONCURRENT,
    )

    n1 = TaskNode(id="read_spec", title="Read Spec", input_keys=[], output_keys=["spec"])
    n2 = TaskNode(id="compile_code", title="Compile Code", input_keys=["spec"], output_keys=["binary"])
    n3 = TaskNode(id="run_tests", title="Run Tests", input_keys=["binary"], output_keys=["test_report"])

    dag.add_node(n1)
    dag.add_node(n2)
    dag.add_node(n3)

    dag.add_edge("read_spec", "compile_code", edge_type=EdgeType.DATA_FLOW, passed_data_keys=["spec"])
    dag.add_edge("compile_code", "run_tests", edge_type=EdgeType.DATA_FLOW, passed_data_keys=["binary"])

    assert dag.get_predecessors("compile_code") == ["read_spec"]
    assert dag.get_successors("compile_code") == ["run_tests"]

    order = dag.topological_sort()
    assert order == ["read_spec", "compile_code", "run_tests"]


def test_cycle_detection():
    dag = TaskDAG(id="cycle-dag", name="Cycle Test")
    dag.add_node(TaskNode(id="A", title="Node A"))
    dag.add_node(TaskNode(id="B", title="Node B"))
    dag.add_node(TaskNode(id="C", title="Node C"))

    dag.add_edge("A", "B")
    dag.add_edge("B", "C")

    # Adding C -> A should raise cycle detection error
    with pytest.raises(ValueError, match="Cycle detected"):
        dag.add_edge("C", "A")


def test_serialization_roundtrip():
    dag = TaskDAG(id="dag-serial", name="Serialization Check")
    dag.add_node(TaskNode(id="step1", title="Step 1", output_keys=["k1"]))
    dag.add_node(TaskNode(id="step2", title="Step 2", input_keys=["k1"]))
    dag.add_edge("step1", "step2")

    # JSON roundtrip
    json_str = dag.to_json()
    data = json.loads(json_str)
    assert data["id"] == "dag-serial"
    assert len(data["nodes"]) == 2

    restored = TaskDAG.from_json(json_str)
    assert restored.id == dag.id
    assert restored.topological_sort() == ["step1", "step2"]

    # YAML roundtrip
    yaml_str = dag.to_yaml()
    assert "dag-serial" in yaml_str
    restored_yaml = TaskDAG.from_yaml(yaml_str)
    assert restored_yaml.id == dag.id
    assert len(restored_yaml.edges) == 1
