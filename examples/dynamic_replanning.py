"""Example: Simulating Runtime Deviation and Dynamic DAG Replanning."""

import asyncio

from taskdag.core.models import TaskDAG, TaskNode
from taskdag.engine.compactor import LosslessContextCompactor
from taskdag.engine.scheduler import AsyncDAGScheduler


async def main():
    print("--- 1. Initialize Fragile Pipeline ---")
    dag = TaskDAG(id="db_setup", name="Database Migration Pipeline")
    dag.add_node(TaskNode(id="provision_db", title="Provision Postgres Instance", output_keys=["db_uri"]))
    dag.add_node(TaskNode(id="run_migrations", title="Run Alembic Migrations", input_keys=["db_uri"]))
    dag.add_edge("provision_db", "run_migrations")

    compactor = LosslessContextCompactor()
    scheduler = AsyncDAGScheduler(dag=dag, compactor=compactor)

    fail_counter = {"attempts": 0}

    async def fragile_migration(node, c):
        fail_counter["attempts"] += 1
        if fail_counter["attempts"] == 1:
            raise RuntimeError("Missing dependency: psycopg2-binary not installed in target environment")
        return {"migrations_applied": 14}

    scheduler.register_handler("run_migrations", fragile_migration)

    print("--- 2. Execute with Dynamic Replanner Enabled ---")
    state = await scheduler.execute()

    print(f"Total Replanning Events: {len(state.replanning_events)}")
    for ev in state.replanning_events:
        print(f"  Event:  {ev.event_id}")
        print(f"  Action: {ev.action_type.value}")
        print(f"  Reason: {ev.reason}")
        print(f"  Nodes Added: {ev.nodes_added}")

    print("\n--- 3. Final Topological Order ---")
    print(" -> ".join(dag.topological_sort()))
    print(f"Global Status: {state.status}")


if __name__ == "__main__":
    asyncio.run(main())
