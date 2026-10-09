"""Example: Subtask Separability Analysis and Basic DAG Execution."""

import asyncio

from taskdag.core.separability import SeparabilityAnalyzer
from taskdag.engine.scheduler import AsyncDAGScheduler


async def main():
    print("--- 1. Subtask Separability Analysis ---")
    analyzer = SeparabilityAnalyzer(separability_threshold=0.50)

    subtasks = [
        {"id": "fetch_spec", "title": "Fetch Specification", "read_keys": ["url"], "write_keys": ["spec_doc"]},
        {"id": "build_client", "title": "Build Client Library", "read_keys": ["spec_doc"], "write_keys": ["client_wheel"]},
        {"id": "build_server", "title": "Build Stub Server", "read_keys": ["spec_doc"], "write_keys": ["server_binary"]},
    ]

    analysis = analyzer.analyze("codegen_service", subtasks)
    print(f"Separability Score S(T): {analysis.separability_score:.3f}")
    print(f"Recommended Mode:        {analysis.recommended_mode.value}")
    print(f"Rationale:               {analysis.rationale}\n")

    print("--- 2. Synthesize and Execute TaskDAG ---")
    dag = analyzer.synthesize_dag("codegen_service", "Client/Server Generation", subtasks)
    scheduler = AsyncDAGScheduler(dag=dag, max_concurrency=2)

    state = await scheduler.execute()
    print(f"Execution Status: {state.status}")
    print(f"Completed Nodes:  {state.completed_nodes}")


if __name__ == "__main__":
    asyncio.run(main())
