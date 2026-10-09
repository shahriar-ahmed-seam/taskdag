"""Example: Bi-directional LangGraph StateGraph Conversion."""

from taskdag.adapters.langgraph import LangGraphAdapter
from taskdag.core.models import TaskDAG, TaskNode


def main():
    print("--- 1. Convert LangGraph Dict Spec to TaskDAG ---")
    langgraph_spec = {
        "name": "Document Summarization Graph",
        "nodes": {
            "extract_pdf": {"title": "Extract Text", "output_keys": ["raw_text"]},
            "chunk_text": {"title": "Chunk Text", "input_keys": ["raw_text"], "output_keys": ["chunks"]},
            "summarize": {"title": "Map-Reduce Summary", "input_keys": ["chunks"], "output_keys": ["summary"]},
        },
        "edges": [
            {"source": "extract_pdf", "target": "chunk_text"},
            {"source": "chunk_text", "target": "summarize"},
        ],
    }

    dag = LangGraphAdapter.to_taskdag(langgraph_spec, dag_id="lg_doc_summary")
    print(f"TaskDAG ID:    {dag.id}")
    print(f"Nodes Count:   {len(dag.nodes)}")
    print(f"Topological:   {' -> '.join(dag.topological_sort())}\n")

    print("--- 2. Export Native TaskDAG Back to LangGraph ---")
    native_dag = TaskDAG(id="native_pipeline", name="Analytics Pipeline")
    native_dag.add_node(TaskNode(id="step_a", title="Step A"))
    native_dag.add_node(TaskNode(id="step_b", title="Step B"))
    native_dag.add_edge("step_a", "step_b")

    exported = LangGraphAdapter.from_taskdag(native_dag)
    print(f"Exported Name:  {exported['name']}")
    print(f"Entry Point:    {exported['entry_point']}")
    print(f"Exported Edges: {exported['edges']}")


if __name__ == "__main__":
    main()
