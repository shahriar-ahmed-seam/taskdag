"""Unit tests for Subtask Separability Analysis and DAG synthesis."""

from taskdag.core.separability import SeparabilityAnalyzer
from taskdag.core.types import ExecutionMode


def test_separable_tasks_detection():
    analyzer = SeparabilityAnalyzer(separability_threshold=0.50)

    # Disjoint tasks with orthogonal read/write sets
    subtasks = [
        {
            "id": "frontend_build",
            "title": "Build Web Assets",
            "read_keys": ["ts_sources", "css_tokens"],
            "write_keys": ["dist_bundle"],
        },
        {
            "id": "backend_build",
            "title": "Build API Service",
            "read_keys": ["py_sources", "db_migrations"],
            "write_keys": ["api_container"],
        },
    ]

    analysis = analyzer.analyze("polyglot_build", subtasks)

    assert analysis.is_separable is True
    assert analysis.recommended_mode == ExecutionMode.DYNAMIC_DAG_CONCURRENT
    assert analysis.overlap_ratio == 0.0
    assert analysis.separability_score == 1.0


def test_tightly_coupled_tasks_trigger_monolith():
    analyzer = SeparabilityAnalyzer(separability_threshold=0.50)

    # Tightly coupled tasks with shared mutable state and feedback loop
    subtasks = [
        {
            "id": "code_kernel",
            "title": "Modify Kernel Memory",
            "read_keys": ["mmu_table", "page_allocator"],
            "write_keys": ["mmu_table", "page_allocator"],
            "interactive_feedback": True,
        },
        {
            "id": "debug_allocator",
            "title": "Debug Page Allocator",
            "read_keys": ["page_allocator", "mmu_table"],
            "write_keys": ["page_allocator", "fault_trace"],
            "interactive_feedback": True,
        },
    ]

    analysis = analyzer.analyze("kernel_debug", subtasks)

    assert analysis.is_separable is False
    assert analysis.recommended_mode == ExecutionMode.SINGLE_AGENT_MONOLITH
    assert analysis.separability_score < 0.50
    assert "Single agent execution recommended" in analysis.rationale


def test_dag_synthesis_producer_consumer_edges():
    analyzer = SeparabilityAnalyzer()

    subtasks = [
        {
            "id": "extract",
            "title": "Extract Raw Data",
            "read_keys": ["raw_url"],
            "write_keys": ["raw_json"],
        },
        {
            "id": "transform",
            "title": "Transform Data",
            "read_keys": ["raw_json"],
            "write_keys": ["clean_parquet"],
        },
        {
            "id": "load",
            "title": "Load to Warehouse",
            "read_keys": ["clean_parquet"],
            "write_keys": ["db_record_count"],
        },
    ]

    dag = analyzer.synthesize_dag("etl_pipeline", "ETL Workflow", subtasks)

    assert len(dag.nodes) == 3
    assert len(dag.edges) == 2
    assert dag.topological_sort() == ["extract", "transform", "load"]
