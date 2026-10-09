"""Unit and integration tests for AsyncDAGScheduler."""

import pytest

from taskdag.core.models import TaskDAG, TaskNode
from taskdag.core.types import EdgeType, ExecutionMode, NodeStatus
from taskdag.engine.scheduler import AsyncDAGScheduler


@pytest.mark.asyncio
async def test_scheduler_concurrent_execution():
    dag = TaskDAG(
        id="async-dag-1",
        name="Parallel Data Prep",
        execution_mode=ExecutionMode.DYNAMIC_DAG_CONCURRENT,
    )
    dag.add_node(TaskNode(id="download_a", title="Download A", output_keys=["data_a"]))
    dag.add_node(TaskNode(id="download_b", title="Download B", output_keys=["data_b"]))
    dag.add_node(TaskNode(id="merge", title="Merge", input_keys=["data_a", "data_b"], output_keys=["final"]))

    dag.add_edge("download_a", "merge", edge_type=EdgeType.DATA_FLOW)
    dag.add_edge("download_b", "merge", edge_type=EdgeType.DATA_FLOW)

    scheduler = AsyncDAGScheduler(dag=dag, max_concurrency=2)
    state = await scheduler.execute(run_id="run-concurrent-01")

    assert state.status == "COMPLETED"
    assert "download_a" in state.completed_nodes
    assert "download_b" in state.completed_nodes
    assert "merge" in state.completed_nodes
    assert dag.nodes["merge"].status == NodeStatus.COMPLETED


@pytest.mark.asyncio
async def test_scheduler_dynamic_replan_interception():
    dag = TaskDAG(
        id="async-dag-fail",
        name="Failure Handling",
        execution_mode=ExecutionMode.DYNAMIC_DAG_CONCURRENT,
    )
    dag.add_node(TaskNode(id="step1", title="Initial Step"))
    dag.add_node(TaskNode(id="flaky_step", title="Flaky Step"))
    dag.add_edge("step1", "flaky_step")

    scheduler = AsyncDAGScheduler(dag=dag, max_concurrency=2)

    call_count = {"count": 0}

    async def flaky_handler(node, compactor):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise RuntimeError("Module not found: libsqlite3-dev")
        return {"repaired": True}

    scheduler.register_handler("flaky_step", flaky_handler)

    state = await scheduler.execute(run_id="run-replan-01")

    assert len(state.replanning_events) >= 1
    assert any("remediate_flaky_step" in n for n in dag.nodes)


@pytest.mark.asyncio
async def test_scheduler_monolithic_execution_bypass():
    dag = TaskDAG(
        id="monolith-dag",
        name="Tightly Coupled Kernel",
        execution_mode=ExecutionMode.SINGLE_AGENT_MONOLITH,
    )
    dag.add_node(TaskNode(id="m1", title="Step 1"))
    dag.add_node(TaskNode(id="m2", title="Step 2"))
    dag.add_edge("m1", "m2")

    scheduler = AsyncDAGScheduler(dag=dag)
    state = await scheduler.execute(run_id="run-monolith-01")

    assert state.status == "COMPLETED"
    assert state.completed_nodes == ["m1", "m2"]
