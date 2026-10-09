"""FastAPI server serving the Anti-AI-Slop Developer Console and API endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from taskdag.benchmarks.cmu_benchmark import CMUBenchmarkRunner
from taskdag.core.separability import SeparabilityAnalyzer

app = FastAPI(title="TaskDAG Developer Console", version="0.1.0")

HTML_PATH = Path(__file__).parent / "index.html"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the static anti-AI-slop developer UI dashboard."""
    if not HTML_PATH.exists():
        return HTMLResponse("<h1>UI file not found</h1>", status_code=404)
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/benchmark")
async def get_benchmark(trials: int = 30):
    """Run the CMU benchmark reproduction suite and return statistical report."""
    runner = CMUBenchmarkRunner()
    report = runner.run_suite(num_trials=trials)
    return JSONResponse(content=report.model_dump(mode="json"))


@app.get("/api/separability")
async def evaluate_separability():
    """Evaluate separability on canonical unseen tasks."""
    analyzer = SeparabilityAnalyzer()
    subtasks = [
        {"id": "parse_ast", "read_keys": ["source_code"], "write_keys": ["ast_tree"]},
        {"id": "type_check", "read_keys": ["ast_tree"], "write_keys": ["type_symbols"]},
        {"id": "codegen", "read_keys": ["ast_tree", "type_symbols"], "write_keys": ["llvm_ir"]},
    ]
    analysis = analyzer.analyze("compiler_frontend", subtasks)
    return JSONResponse(content=analysis.model_dump(mode="json"))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "engine": "TaskDAG", "version": "0.1.0"}
