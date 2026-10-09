"""Unit tests for DynamicReplanner and CMU benchmark simulation."""

from taskdag.benchmarks.cmu_benchmark import CMUBenchmarkRunner
from taskdag.core.models import TaskDAG, TaskNode
from taskdag.core.types import ExecutionMode, NodeStatus, ReplanActionType
from taskdag.engine.replanner import DynamicReplanner


def test_replan_inject_remediation():
    dag = TaskDAG(id="test_dag", name="Replanning Pipeline")
    n1 = TaskNode(id="build", title="Build Module")
    n2 = TaskNode(id="test", title="Run Verification")
    dag.add_node(n1)
    dag.add_node(n2)
    dag.add_edge("build", "test")

    replanner = DynamicReplanner()
    event = replanner.replan_on_failure(
        dag=dag,
        failing_node_id="build",
        error_message="Module not found: libclang-18",
    )

    assert event.action_type == ReplanActionType.INJECT_REMEDIATION
    assert len(event.nodes_added) == 1
    remed_id = event.nodes_added[0]

    assert remed_id in dag.nodes
    assert dag.nodes[remed_id].status == NodeStatus.READY
    assert dag.nodes["build"].status == NodeStatus.PENDING

    # Topological sort must succeed and remediation must precede build
    order = dag.topological_sort()
    assert order.index(remed_id) < order.index("build")
    assert order.index("build") < order.index("test")


def test_replan_split_node():
    dag = TaskDAG(id="split_dag", name="Split Pipeline")
    n1 = TaskNode(id="huge_task", title="Huge Task", input_keys=["in1"], output_keys=["out1"])
    n2 = TaskNode(id="final_step", title="Final Step", input_keys=["out1"])
    dag.add_node(n1)
    dag.add_node(n2)
    dag.add_edge("huge_task", "final_step")

    replanner = DynamicReplanner()
    event = replanner.replan_on_failure(
        dag=dag,
        failing_node_id="huge_task",
        error_message="Timeout: Task too large to execute in single pass",
    )

    assert event.action_type == ReplanActionType.SPLIT_NODE
    assert "huge_task" not in dag.nodes
    assert "huge_task_part1" in dag.nodes
    assert "huge_task_part2" in dag.nodes

    order = dag.topological_sort()
    assert order == ["huge_task_part1", "huge_task_part2", "final_step"]


def test_replan_degrade_to_monolith():
    dag = TaskDAG(
        id="concurrent_dag",
        name="Concurrent Plan",
        execution_mode=ExecutionMode.DYNAMIC_DAG_CONCURRENT,
    )
    dag.add_node(TaskNode(id="t1", title="Task 1"))
    dag.add_node(TaskNode(id="t2", title="Task 2"))

    replanner = DynamicReplanner()
    event = replanner.replan_on_failure(
        dag=dag,
        failing_node_id="t1",
        error_message="Concurrency conflict state divergence detected",
    )

    assert event.action_type == ReplanActionType.DEGRADE_TO_MONOLITH
    assert dag.execution_mode == ExecutionMode.SINGLE_AGENT_MONOLITH


def test_cmu_benchmark_runner():
    runner = CMUBenchmarkRunner(seed=123)
    report = runner.run_suite(num_trials=30)

    assert report.total_trials == 30
    assert report.static_success_rate < 0.65  # Static pipeline fails often on unseen tasks
    assert report.taskdag_success_rate > 0.80  # Dynamic replanning raises success steadily higher
    assert report.success_rate_delta > 0.20
    assert report.coordination_tax_reduction > 0.20
    assert report.mean_context_retention >= 0.99
