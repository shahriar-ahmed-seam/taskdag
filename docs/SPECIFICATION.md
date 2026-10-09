# TaskDAG Canonical Specification (RFC-001)

## 1. Overview

This document specifies the canonical schemas, field contracts, validation constraints, and serialization protocols for the TaskDAG framework.

---

## 2. Enumerations

### 2.1 NodeStatus
Represents the discrete lifecycle status of a task node.
- `PENDING`: Awaiting satisfaction of dependency predecessors.
- `READY`: All predecessor dependencies satisfied; queued for dispatch.
- `RUNNING`: Currently active within an execution worker.
- `COMPLETED`: Execution succeeded; postconditions verified.
- `FAILED`: Execution terminated with non-zero exit code or uncaught exception.
- `REPLANNED`: Node was dynamically mutated, decomposed, or superseded.
- `SKIPPED`: Condition evaluated to false; execution bypassed.
- `PRUNED`: Downstream branch cancelled due to upstream failure or obsolescence.

### 2.2 EdgeType
Defines coupling semantics between connected nodes.
- `DEPENDS_ON`: Strict sequential precedence barrier.
- `DATA_FLOW`: Directed transmission of specific context keys.
- `CONDITIONAL_BRANCH`: Conditional path evaluated via predicate.
- `REMEDIATION`: Priority recovery path injected by dynamic replanner.

### 2.3 ExecutionMode
- `SINGLE_AGENT_MONOLITH`: Linear single-agent execution with zero coordination overhead.
- `DYNAMIC_DAG_CONCURRENT`: Concurrently scheduled task graph across asynchronous worker pool.

### 2.4 ReplanActionType
- `SPLIT_NODE`: Partition single complex node into sequential sub-nodes.
- `INJECT_REMEDIATION`: Insert diagnostic/patching node immediately before failed node.
- `REROUTE_DEPENDENCY`: Re-wire edges to alternative provider node.
- `PRUNE_SUBTREE`: Mark unreachable or unviable downstream nodes as PRUNED.
- `DEGRADE_TO_MONOLITH`: Collapse multi-agent graph into single-agent sequence.

---

## 3. Data Schemas

### 3.1 TaskNode Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Unique node identifier matching `^[a-zA-Z0-9_\-]+$`. |
| `title` | `string` | Yes | Concise human-readable title. |
| `description` | `string` | No | Complete task specification. |
| `input_keys` | `list[string]` | No | State keys consumed from parent context. |
| `output_keys` | `list[string]` | No | State keys produced into parent context. |
| `preconditions` | `list[string]` | No | Logical assertions evaluated prior to execution. |
| `postconditions` | `list[string]` | No | Logical assertions evaluated upon completion. |
| `status` | `NodeStatus` | Yes | Current lifecycle state (default `PENDING`). |
| `assigned_agent_id`| `string` | No | Optional assigned worker/agent identifier. |
| `metadata` | `dict` | No | Arbitrary JSON-serializable execution metadata. |
| `retry_count` | `integer` | Yes | Number of attempted executions (>= 0). |
| `max_retries` | `integer` | Yes | Maximum permitted retry attempts (default 2). |
| `result` | `dict` | No | Output payload upon successful completion. |
| `error` | `string` | No | Formatted traceback string if execution failed. |

### 3.2 TaskEdge Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | Yes | Node ID of upstream dependency. |
| `target` | `string` | Yes | Node ID of downstream dependent. |
| `edge_type` | `EdgeType` | Yes | Coupling relationship (default `DEPENDS_ON`). |
| `condition` | `string` | No | Optional predicate evaluated for conditional routing. |
| `passed_data_keys`| `list[string]` | No | Exact context keys forwarded across edge. |

### 3.3 TaskDAG Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Canonical DAG identifier. |
| `name` | `string` | Yes | Human-readable workflow title. |
| `description` | `string` | No | Workflow objective and scope. |
| `execution_mode` | `ExecutionMode`| Yes | Dispatch strategy. |
| `nodes` | `dict[string, TaskNode]` | Yes | Map of node IDs to TaskNode objects. |
| `edges` | `list[TaskEdge]` | Yes | Directed edge set. |
| `metadata` | `dict` | No | Arbitrary workflow metadata. |

#### Invariants:
1. Every edge source and target must exist in the `nodes` mapping.
2. The directed graph must be strictly acyclic ($G = (V, E)$ contains no directed cycles).
3. Topological sort must be deterministically computable via Kahn's algorithm.

---

## 4. Context Compaction Schema

### 4.1 FactItem

| Field | Type | Description |
|---|---|---|
| `key` | `string` | Canonical identifier (e.g., `compiler.version`). |
| `value` | `any` | Validated ground truth value. |
| `source_node` | `string` | Originating node ID. |
| `category` | `string` | Classification: ENVIRONMENT, CODE_SYMBOL, ERROR_DIAGNOSTIC, ARTIFACT_STATE. |
| `confidence` | `float` | Metric confidence bounded in [0.0, 1.0]. |
| `timestamp` | `float` | Epoch timestamp of fact establishment. |

### 4.2 ArtifactDelta

| Field | Type | Description |
|---|---|---|
| `path` | `string` | Canonical workspace filesystem path. |
| `sha256_hash` | `string` | Cryptographic SHA-256 digest of artifact contents. |
| `action` | `string` | Mutation category: CREATED, MODIFIED, or DELETED. |
| `diff_hunk` | `string` | Verbatim unified diff hunk. |
| `byte_size` | `integer` | Byte length of content. |

---

## 5. Serialization Standards

All schemas must support lossless round-trip serialization to both standard JSON (RFC 8259) and YAML (1.2). Deserialization must enforce Pydantic v2 strict schema validation.
