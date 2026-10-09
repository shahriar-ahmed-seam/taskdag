"""Unit tests for LosslessContextCompactor and memory retention."""

from taskdag.engine.compactor import LosslessContextCompactor


def test_fact_registration_and_retention():
    compactor = LosslessContextCompactor()
    compactor.register_fact("compiler.target", "x86_64-linux-gnu", "configure_step")
    compactor.register_fact("python.version", "3.12.3", "env_probe")
    compactor.add_invariant("No root user executions")

    ground_truth = {"compiler.target", "python.version"}
    ratio = compactor.evaluate_retention_ratio(ground_truth)
    assert ratio == 1.0

    rendered = compactor.render_prompt()
    assert "compiler.target = x86_64-linux-gnu" in rendered
    assert "No root user executions" in rendered


def test_artifact_delta_checksum_and_diff():
    compactor = LosslessContextCompactor()
    patch = "+def new_handler():\n+    return 200"
    compactor.record_artifact("src/server.py", "def new_handler(): return 200", diff_hunk=patch)

    context = compactor.build_compacted_context("ctx-01")
    assert "src/server.py" in context.artifacts
    delta = context.artifacts["src/server.py"]
    assert delta.diff_hunk == patch
    assert len(delta.sha256_hash) == 64


def test_fault_telemetry_capture():
    compactor = LosslessContextCompactor()
    compactor.record_telemetry(
        node_id="test_runner",
        command="pytest tests/test_core.py",
        exit_code=1,
        stdout="Running tests...\n1 failed\nTraceback (most recent call last):\n  File 'test_core.py', line 12: assert 0 == 1\nAssertionError: assert 0 == 1",
        stderr="Process terminated with exit status 1",
    )

    rendered = compactor.render_prompt()
    assert "Node 'test_runner' failed (exit 1)" in rendered
    assert "AssertionError" in rendered


def test_retention_ratio_lossy_comparison():
    compactor = LosslessContextCompactor()
    all_facts = {
        "db_host": "127.0.0.1",
        "db_port": 5432,
        "migration_version": "v1.4.2",
        "auth_token_secret": "sec_k8912",
        "api_endpoint": "https://api.internal/v1",
    }
    for k, v in all_facts.items():
        compactor.register_fact(k, v, "node_setup")

    # Structured compactor retains 100% of facts
    assert compactor.evaluate_retention_ratio(set(all_facts.keys())) == 1.0

    # Simulated lossy persona summary where only 2 facts are remembered
    lossy_retained = {"db_host", "api_endpoint"}
    lossy_ratio = len(lossy_retained) / len(all_facts)
    assert lossy_ratio == 0.40  # 40% retention in naive conversational handoffs
