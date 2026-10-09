"""Unit tests for CLI commands and Developer Console API server."""

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from taskdag.cli.main import app
from taskdag.ui.server import app as fastapi_app

runner = CliRunner()


def test_cli_plan_command():
    result = runner.invoke(app, ["plan", "--task-id", "compiler_frontend"])
    assert result.exit_code == 0
    assert "Separability Metrics" in result.output
    assert "Separability Score S(T)" in result.output


def test_cli_run_command():
    result = runner.invoke(app, ["run", "--mode", "concurrent"])
    assert result.exit_code == 0
    assert "Execution Summary" in result.output
    assert "Global Status:" in result.output


def test_cli_replan_command():
    result = runner.invoke(app, ["replan", "--failing-node", "compile_step"])
    assert result.exit_code == 0
    assert "Replanning Mutation Event" in result.output
    assert "INJECT_REMEDIATION" in result.output


def test_cli_compact_command():
    result = runner.invoke(app, ["compact"])
    assert result.exit_code == 0
    assert "Lossless Context Compaction Engine" in result.output
    assert "Fact Retention Ratio R(C)" in result.output


def test_cli_benchmark_command():
    result = runner.invoke(app, ["benchmark", "--trials", "5"])
    assert result.exit_code == 0
    assert "CMU Benchmark Reproduction Results" in result.output
    assert "TaskDAG" in result.output
    assert "Replanning" in result.output


def test_ui_api_endpoints():
    client = TestClient(fastapi_app)

    # Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # HTML Index check
    res_html = client.get("/")
    assert res_html.status_code == 200
    assert "TaskDAG" in res_html.text

    # Separability API
    res_sep = client.get("/api/separability")
    assert res_sep.status_code == 200
    assert "separability_score" in res_sep.json()

    # Benchmark API
    res_bm = client.get("/api/benchmark?trials=5")
    assert res_bm.status_code == 200
    assert "taskdag_success_rate" in res_bm.json()
