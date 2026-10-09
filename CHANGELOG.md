# Changelog

All notable changes to this project are documented in this file following the Keep a Changelog specification.

## [0.1.0] - 2026-10-10

### Added
- Canonical TaskDAG Pydantic v2 data models: TaskNode, TaskEdge, TaskDAG, ExecutionState, SubtaskSeparabilityAnalysis.
- Topological cycle detection and Kahn's algorithm ordering.
- Subtask Separability Analyzer calculating state overlap ratio and decision score S(T).
- Single-agent execution bypass for non-separable subtasks to eliminate coordination tax.
- LosslessContextCompactor preserving verified state facts, AST diff hunks, and telemetry tails.
- DynamicReplanner with graph mutation operators: INJECT_REMEDIATION, SPLIT_NODE, PRUNE_SUBTREE, DEGRADE_TO_MONOLITH.
- CMU benchmark reproduction harness validating the increase in unseen task completion rates from approximately 25% to over 85%.
- AsyncDAGScheduler with topological wave concurrency and live event streaming.
- Ecosystem adapters for LangGraph, CrewAI, and OpenTelemetry JSONL traces.
- Production Typer and Rich CLI supporting plan, run, replan, compact, benchmark, and serve commands.
- Anti-AI-slop developer UI console with dark neutral design (#090b0e) and live API telemetry.
