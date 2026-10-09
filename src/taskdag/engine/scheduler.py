"""Asynchronous DAG Scheduler and Execution Pipeline.

Executes TaskDAG workflows with concurrency control, dynamic runtime replanning,
and lossless context compaction.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from taskdag.core.models import (
    ExecutionState,
    TaskDAG,
    TaskNode,
)
from taskdag.core.types import (
    ExecutionMode,
    NodeStatus,
)
from taskdag.engine.compactor import LosslessContextCompactor
from taskdag.engine.replanner import DynamicReplanner

AsyncNodeHandler = Callable[[TaskNode, LosslessContextCompactor], Awaitable[Dict[str, Any]]]


class AsyncDAGScheduler:
    """Asynchronously schedules and executes TaskDAG nodes adhering to dependency waves."""

    def __init__(
        self,
        dag: TaskDAG,
        max_concurrency: int = 4,
        replanner: Optional[DynamicReplanner] = None,
        compactor: Optional[LosslessContextCompactor] = None,
    ):
        self.dag = dag
        self.max_concurrency = max_concurrency
        self.replanner = replanner or DynamicReplanner()
        self.compactor = compactor or LosslessContextCompactor()
        self._handlers: Dict[str, AsyncNodeHandler] = {}
        self._default_handler: Optional[AsyncNodeHandler] = None
        self._event_listeners: List[Callable[[str, Dict[str, Any]], None]] = []

    def register_handler(self, node_id: str, handler: AsyncNodeHandler) -> None:
        """Register a specific async callable for a given node ID."""
        self._handlers[node_id] = handler

    def set_default_handler(self, handler: AsyncNodeHandler) -> None:
        """Register fallback handler for nodes without custom callables."""
        self._default_handler = handler

    def add_event_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        """Attach listener for runtime lifecycle events (node_start, node_complete, replan)."""
        self._event_listeners.append(listener)

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        for listener in self._event_listeners:
            try:
                listener(event_type, payload)
            except Exception:
                pass

    async def _default_node_execution(
        self,
        node: TaskNode,
        compactor: LosslessContextCompactor,
    ) -> Dict[str, Any]:
        """Default mock execution for demonstrations and tests."""
        await asyncio.sleep(0.01)
        # Verify preconditions
        for pre in node.preconditions:
            if pre not in compactor._invariants and pre not in compactor._facts:
                raise ValueError(f"Precondition '{pre}' not met before executing '{node.id}'")

        # Simulate work output
        output_data: Dict[str, Any] = {}
        for k in node.output_keys:
            output_data[k] = f"val_for_{k}_{node.id}"
            compactor.register_fact(k, output_data[k], node.id)

        return output_data

    async def execute(self, run_id: Optional[str] = None) -> ExecutionState:
        """
        Execute the DAG to completion.
        Supports dynamic runtime replanning if any node raises an exception.
        """
        run_id = run_id or f"run-{int(time.time()*1000)}"
        start_time = time.time()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        state = ExecutionState(
            run_id=run_id,
            dag_id=self.dag.id,
            mode=self.dag.execution_mode,
            status="RUNNING",
            start_time=start_time,
        )

        # Monolithic single-agent execution optimization
        if self.dag.execution_mode == ExecutionMode.SINGLE_AGENT_MONOLITH:
            return await self._execute_monolith(state)

        active_tasks: Dict[str, asyncio.Task[None]] = {}

        while True:
            # Check terminal state: all nodes completed, pruned, or failed without replan
            all_done = True
            for node in self.dag.nodes.values():
                if node.status in [NodeStatus.PENDING, NodeStatus.READY, NodeStatus.RUNNING]:
                    all_done = False
                    break

            if all_done and not active_tasks:
                break

            # Find ready nodes whose predecessors have completed successfully
            ready_nodes: List[TaskNode] = []
            for nid, node in self.dag.nodes.items():
                if node.status in [NodeStatus.PENDING, NodeStatus.READY] and nid not in active_tasks:
                    predecessors = self.dag.get_predecessors(nid)
                    preds_finished = all(
                        self.dag.nodes[p].status == NodeStatus.COMPLETED
                        for p in predecessors
                        if p in self.dag.nodes
                    )
                    if preds_finished:
                        node.status = NodeStatus.READY
                        ready_nodes.append(node)

            # Dispatch ready nodes
            for node in ready_nodes:
                async def _run_wrapper(n: TaskNode) -> None:
                    async with semaphore:
                        n.status = NodeStatus.RUNNING
                        self._emit("node_start", {"node_id": n.id, "run_id": run_id})
                        handler = self._handlers.get(n.id) or self._default_handler or self._default_node_execution

                        try:
                            res = await handler(n, self.compactor)
                            n.result = res
                            n.status = NodeStatus.COMPLETED
                            state.completed_nodes.append(n.id)
                            self._emit("node_complete", {"node_id": n.id, "result": res})
                        except Exception as exc:
                            error_str = str(exc)
                            n.error = error_str
                            n.status = NodeStatus.FAILED
                            state.failed_nodes.append(n.id)
                            self._emit("node_failed", {"node_id": n.id, "error": error_str})

                            # Invoke dynamic replanner
                            replan_event = self.replanner.replan_on_failure(
                                dag=self.dag,
                                failing_node_id=n.id,
                                error_message=error_str,
                                compactor=self.compactor,
                            )
                            state.replanning_events.append(replan_event)
                            self._emit("replan", {"event": replan_event.model_dump(mode="json")})

                task = asyncio.create_task(_run_wrapper(node))
                active_tasks[node.id] = task

            if not active_tasks:
                # No active tasks and no ready nodes -> check if any pending nodes are blocked
                break

            # Wait for any active task to finish
            done, _ = await asyncio.wait(
                active_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Clean up completed tasks
            for finished_task in done:
                for nid, t in list(active_tasks.items()):
                    if t == finished_task:
                        del active_tasks[nid]

        state.end_time = time.time()
        has_failed = any(n.status == NodeStatus.FAILED for n in self.dag.nodes.values())
        state.status = "FAILED" if has_failed else "COMPLETED"
        compacted = self.compactor.build_compacted_context(f"ctx-{run_id}")
        state.context_store = compacted.model_dump(mode="json")
        return state

    async def _execute_monolith(self, state: ExecutionState) -> ExecutionState:
        """Sequential single-agent execution with zero multi-agent synchronization tax."""
        order = self.dag.topological_sort()
        for nid in order:
            node = self.dag.nodes[nid]
            node.status = NodeStatus.RUNNING
            self._emit("node_start", {"node_id": nid, "mode": "monolith"})
            handler = self._handlers.get(nid) or self._default_handler or self._default_node_execution

            try:
                res = await handler(node, self.compactor)
                node.result = res
                node.status = NodeStatus.COMPLETED
                state.completed_nodes.append(nid)
                self._emit("node_complete", {"node_id": nid})
            except Exception as exc:
                node.status = NodeStatus.FAILED
                node.error = str(exc)
                state.failed_nodes.append(nid)
                replan_event = self.replanner.replan_on_failure(
                    dag=self.dag,
                    failing_node_id=nid,
                    error_message=str(exc),
                    compactor=self.compactor,
                )
                state.replanning_events.append(replan_event)
                # Retry if remediation node injected
                break

        state.end_time = time.time()
        state.status = "COMPLETED" if not state.failed_nodes else "FAILED"
        compacted = self.compactor.build_compacted_context(f"ctx-{state.run_id}")
        state.context_store = compacted.model_dump(mode="json")
        return state
