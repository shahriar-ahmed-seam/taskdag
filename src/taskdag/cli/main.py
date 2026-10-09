"""Production CLI for TaskDAG using Typer and Rich."""

from __future__ import annotations

import asyncio

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from taskdag.benchmarks.cmu_benchmark import CMUBenchmarkRunner
from taskdag.core.models import TaskDAG, TaskNode
from taskdag.core.separability import SeparabilityAnalyzer
from taskdag.core.types import ExecutionMode
from taskdag.engine.compactor import LosslessContextCompactor
from taskdag.engine.replanner import DynamicReplanner
from taskdag.engine.scheduler import AsyncDAGScheduler

app = typer.Typer(
    name="taskdag",
    help="TaskDAG: Per-Task Dynamic DAG Engine with Lossless Context Compaction and Runtime Replanning",
    no_args_is_help=True,
)
console = Console()


@app.command()
def plan(
    task_id: str = typer.Option("compiler_service", help="Task objective identifier"),
    threshold: float = typer.Option(0.50, help="Separability threshold"),
):
    """Analyze subtask separability and determine single-agent monolith vs concurrent DAG."""
    console.print(Panel(f"[bold cyan]TaskDAG Separability Analysis[/bold cyan] for [yellow]{task_id}[/yellow]", border_style="blue"))

    sample_subtasks = [
        {"id": "parse_syntax", "title": "Parse Syntax", "read_keys": ["raw_source"], "write_keys": ["ast"]},
        {"id": "type_check", "title": "Type Check", "read_keys": ["ast"], "write_keys": ["typed_ast"]},
        {"id": "emit_bytecode", "title": "Emit Bytecode", "read_keys": ["typed_ast"], "write_keys": ["pyc"]},
    ]

    analyzer = SeparabilityAnalyzer(separability_threshold=threshold)
    analysis = analyzer.analyze(task_id, sample_subtasks)

    table = Table(title="Separability Metrics", border_style="dim")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold green")

    table.add_row("Total Context Keys", str(len(analysis.total_context_keys)))
    table.add_row("State Overlap Keys", str(len(analysis.context_overlap_keys)))
    table.add_row("Overlap Ratio", f"{analysis.overlap_ratio:.1%}")
    table.add_row("Separability Score S(T)", f"{analysis.separability_score:.3f}")
    table.add_row("Threshold", f"{threshold:.2f}")
    table.add_row("Is Separable?", "[green]YES[/green]" if analysis.is_separable else "[red]NO[/red]")
    table.add_row("Recommended Mode", f"[bold]{analysis.recommended_mode.value}[/bold]")

    console.print(table)
    console.print(f"[bold]Rationale:[/bold] {analysis.rationale}\n")


@app.command()
def run(
    mode: str = typer.Option("concurrent", help="Execution mode: concurrent or monolith"),
    max_workers: int = typer.Option(4, help="Maximum concurrent workers"),
):
    """Execute a task workflow through the asynchronous DAG scheduler."""
    console.print(Panel("[bold green]Executing TaskDAG Workflow[/bold green]", border_style="green"))

    exec_mode = ExecutionMode.DYNAMIC_DAG_CONCURRENT if mode == "concurrent" else ExecutionMode.SINGLE_AGENT_MONOLITH
    dag = TaskDAG(id="cli_demo", name="CLI Demo Workflow", execution_mode=exec_mode)
    dag.add_node(TaskNode(id="fetch_data", title="Fetch Data", output_keys=["raw_data"]))
    dag.add_node(TaskNode(id="clean_data", title="Clean Data", input_keys=["raw_data"], output_keys=["clean_data"]))
    dag.add_node(TaskNode(id="train_model", title="Train Model", input_keys=["clean_data"], output_keys=["weights"]))
    dag.add_edge("fetch_data", "clean_data")
    dag.add_edge("clean_data", "train_model")

    scheduler = AsyncDAGScheduler(dag=dag, max_concurrency=max_workers)

    async def _execute():
        return await scheduler.execute()

    state = asyncio.run(_execute())

    table = Table(title="Execution Summary", border_style="dim")
    table.add_column("Node ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Retries")

    for nid in dag.topological_sort():
        node = dag.nodes[nid]
        status_style = "green" if node.status.value == "COMPLETED" else "red"
        table.add_row(nid, f"[{status_style}]{node.status.value}[/{status_style}]", str(node.retry_count))

    console.print(table)
    console.print(f"[bold]Global Status:[/bold] [green]{state.status}[/green] in {state.end_time - state.start_time:.3f}s\n")


@app.command()
def replan(
    failing_node: str = typer.Option("compile_step", help="Node to simulate failure on"),
    error: str = typer.Option("Module not found: libclang-18", help="Error message to simulate"),
):
    """Simulate a runtime failure and inspect dynamic DAG replanning mutations."""
    console.print(Panel(f"[bold yellow]Simulating Runtime Failure on '{failing_node}'[/bold yellow]", border_style="yellow"))

    dag = TaskDAG(id="replan_demo", name="Replanning Demo")
    dag.add_node(TaskNode(id="prep", title="Prepare Environment"))
    dag.add_node(TaskNode(id=failing_node, title="Compile Module"))
    dag.add_node(TaskNode(id="verify", title="Run Verification"))
    dag.add_edge("prep", failing_node)
    dag.add_edge(failing_node, "verify")

    replanner = DynamicReplanner()
    event = replanner.replan_on_failure(
        dag=dag,
        failing_node_id=failing_node,
        error_message=error,
    )

    table = Table(title="Replanning Mutation Event", border_style="dim")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Action Type", f"[magenta]{event.action_type.value}[/magenta]")
    table.add_row("Trigger Node", event.trigger_node_id)
    table.add_row("Nodes Added", ", ".join(event.nodes_added))
    table.add_row("Reason", event.reason)
    table.add_row("New Topological Order", " -> ".join(dag.topological_sort()))

    console.print(table)
    console.print("[green]DAG acyclicity and topological invariants successfully maintained.[/green]\n")


@app.command()
def compact():
    """Demonstrate lossless context compaction and memory retention."""
    console.print(Panel("[bold cyan]Lossless Context Compaction Engine[/bold cyan]", border_style="blue"))

    compactor = LosslessContextCompactor()
    compactor.register_fact("compiler.version", "clang-18.1.0", "probe_env")
    compactor.register_fact("optimization.level", "-O3", "config_step")
    compactor.add_invariant("Execution must not exceed 2048 MB memory")
    compactor.record_artifact(
        "src/core.c",
        "int main() { return 0; }",
        diff_hunk="+int main() { return 0; }",
    )

    ground_truth = {"compiler.version", "optimization.level"}
    retention = compactor.evaluate_retention_ratio(ground_truth)

    context = compactor.build_compacted_context("ctx-demo")

    table = Table(title="Compaction Inspection", border_style="dim")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold green")

    table.add_row("Fact Retention Ratio R(C)", f"{retention:.1%}")
    table.add_row("Active Invariants", str(len(context.active_invariants)))
    table.add_row("Artifact Diffs Preserved", str(len(context.artifacts)))
    table.add_row("Token Compression Ratio", f"{context.compression_ratio}x")

    console.print(table)
    console.print("[bold]Rendered Compaction Frame:[/bold]")
    console.print(compactor.render_prompt(), markup=False)


@app.command()
def benchmark(
    trials: int = typer.Option(40, help="Number of benchmark trials to run"),
):
    """Run CMU benchmark reproduction suite contrasting static roles vs TaskDAG."""
    console.print(Panel(f"[bold green]Running CMU Benchmark Suite ({trials} trials)[/bold green]", border_style="green"))

    runner = CMUBenchmarkRunner()
    report = runner.run_suite(num_trials=trials)

    table = Table(title="CMU Benchmark Reproduction Results", border_style="dim")
    table.add_column("System Architecture", style="cyan")
    table.add_column("Success Rate", style="bold")
    table.add_column("Mean Tokens", style="dim")
    table.add_column("Coordination Overhead", style="dim")

    table.add_row(
        "Static Frozen Role Pipeline",
        f"[red]{report.static_success_rate:.1%}[/red]",
        f"{report.static_mean_tokens:.0f}",
        "High (Persona Telephone Game)",
    )
    table.add_row(
        "TaskDAG (Dynamic Replanning)",
        f"[green]{report.taskdag_success_rate:.1%}[/green]",
        f"{report.taskdag_mean_tokens:.0f}",
        f"Reduced by {report.coordination_tax_reduction:.1%}",
    )

    console.print(table)
    console.print(f"[bold green]Net Success Rate Improvement:[/bold green] +{report.success_rate_delta:.1%}")
    console.print(f"[bold cyan]Context Retention Ratio:[/bold cyan] {report.mean_context_retention:.1%}\n")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host address"),
    port: int = typer.Option(8000, help="Port number"),
):
    """Launch the Anti-AI-Slop Developer UI Console and API server."""
    console.print(Panel(f"[bold blue]Launching TaskDAG Developer Console on http://{host}:{port}[/bold blue]", border_style="blue"))
    uvicorn.run("taskdag.ui.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
