# TaskDAG System Architecture

## 1. Problem Statement & Root Cause Analysis

Traditional multi-agent architectures (such as AutoGen, CrewAI, ChatDev, and MetaGPT) assign static persona roles (e.g., Product Manager, Software Engineer, Code Reviewer, QA Specialist) in hard-coded sequential pipelines. While intuitive from a human organizational perspective, this approach fails on unseen real-world tasks due to three systemic failure modes:

```
+-------------------------------------------------------------+
|              Hard-coded Task Shape Assumption               |
+-------------------------------------------------------------+
          |                         |                        |
          v                         v                        v
+--------------------+    +--------------------+    +--------------------+
|  Structural Prior  |    |   Lossy Context    |    |    Unnecessary     |
|      Mismatch      |    |      Handoffs      |    |  Coordination Tax  |
+--------------------+    +--------------------+    +--------------------+
| Frozen pipeline    |    | Role boundaries    |    | Paying multi-agent |
| assumes spec-code- |    | drop critical      |    | overhead when      |
| test; cannot adapt |    | facts, diffs, and  |    | subtasks are not   |
| or replan.         |    | error traces.      |    | truly separable.   |
+--------------------+    +--------------------+    +--------------------+
```

### 1.1 Structural Prior Mismatch
A frozen waterfall pipeline imposes a rigid topology on problems that inherently demand non-linear discovery, backtracking, and dynamic tool invocation. When an unexpected runtime failure emerges (e.g., missing system dependency, schema divergence, compilation error), the static pipeline cannot adapt or re-wire dependencies.

### 1.2 Lossy Context Handoffs
Passing natural language summaries between persona boundaries introduces prompt degradation. Downstream agents lose verified file paths, AST diff hunks, exit codes, and environmental invariants, forcing subsequent agents to hallucinate state.

### 1.3 Unnecessary Coordination Tax
Decomposing non-separable subtasks across multiple LLM agents inflates token consumption, introduces latency serialization, and risks consensus deadlocks. As established empirically: single agents outperform multi-agent teams unless subtasks are truly separable.

---

## 2. Core Architectural Rules

TaskDAG replaces static role hierarchies with dynamic per-task execution graphs governed by three non-negotiable rules:

1. **Decompose tasks by DAG, not job titles.**
   Subtasks are isolated by mathematical dependency analysis (read/write sets) rather than arbitrary human job titles.
2. **Preserve context with single-agent compaction.**
   State is stored in a structured, lossless memory ledger (verified facts, SHA-256 artifact diffs, invariant constraints) rather than lossy conversational summaries.
3. **Enable dynamic replanning when reality deviates.**
   Runtime exceptions and invariant breaches trigger deterministic DAG mutations (node remediation, node splitting, edge rewiring, or degradation to monolith).

---

## 3. Subsystem Blueprint

```
+--------------------------------------------------------------------------+
|                              TaskDAG Engine                              |
+--------------------------------------------------------------------------+
|                                                                          |
|  [Input Task Objective]                                                  |
|           |                                                              |
|           v                                                              |
|  +--------------------------------------------------------------------+  |
|  | Subtask Separability Analyzer                                      |  |
|  | S(T) = 1 - (alpha * OverlapRatio + (1 - alpha) * Coupling)          |  |
|  +--------------------------------------------------------------------+  |
|       |                                               |                  |
|       | S(T) < threshold                              | S(T) >= threshold|
|       v                                               v                  |
|  +--------------------------+               +-----------------------+    |
|  | Single-Agent Monolith    |               | Concurrent TaskDAG    |    |
|  | (Zero Coordination Tax)  |               | (Topological Waves)   |    |
|  +--------------------------+               +-----------------------+    |
|       |                                               |                  |
|       +-----------------------+-----------------------+                  |
|                               |                                          |
|                               v                                          |
|  +--------------------------------------------------------------------+  |
|  | Async DAG Scheduler & Execution Pipeline                           |  |
|  | - Concurrency Control (Semaphore)                                 |  |
|  | - Topological Wave Dispatch                                        |  |
|  +--------------------------------------------------------------------+  |
|       |                                   ^                              |
|       | Runtime Deviation / Exception     | Dynamic DAG Mutation         |
|       v                                   |                              |
|  +--------------------------------------------------------------------+  |
|  | Dynamic Runtime Replanner                                          |  |
|  | - Failure Diagnosis                                                |  |
|  | - INJECT_REMEDIATION / SPLIT_NODE / PRUNE_SUBTREE / DEGRADE         |  |
|  | - Invariant & Cycle Verification                                  |  |
|  +--------------------------------------------------------------------+  |
|       |                                                                  |
|       v                                                                  |
|  +--------------------------------------------------------------------+  |
|  | Lossless Context Compactor                                         |  |
|  | - FactRegistry (Ground-truth verified values)                      |  |
|  | - ArtifactDeltaStore (SHA-256, AST diffs)                          |  |
|  | - ExecutionTraceTail (Structured exit codes & error snippets)      |  |
|  +--------------------------------------------------------------------+  |
|                                                                          |
+--------------------------------------------------------------------------+
```

---

## 4. Subtask Separability Formulation

To eliminate unnecessary coordination tax, TaskDAG evaluates whether a task decomposition is separable before spawning concurrent workflows.

Let $T = \{T_1, T_2, \dots, T_n\}$ denote proposed subtasks. Each subtask $T_i$ defines a read set $R(T_i)$ and a write set $W(T_i)$.

### 4.1 State Overlap Key Set
The mutable overlap key set $O(T)$ represents read-after-write, write-after-read, and write-after-write conflicts:

$$O(T) = \bigcup_{i \ne j} \left( (W(T_i) \cap R(T_j)) \cup (R(T_i) \cap W(T_j)) \cup (W(T_i) \cap W(T_j)) \right) \setminus I_{shared}$$

where $I_{shared}$ denotes declared immutable shared invariants.

### 4.2 Overlap Ratio
$$\rho(T) = \frac{|O(T)|}{|\bigcup_i (R(T_i) \cup W(T_i))|}$$

### 4.3 Separability Score
Given coupling coefficient $\kappa \in [0, 1]$ representing feedback loops (e.g. interactive REPL debugging):

$$S(T) = \max\left(0, 1 - (\alpha \cdot \rho(T) + (1 - \alpha) \cdot \kappa)\right)$$

### 4.4 Decision Rule
$$\text{Dispatch Mode} = \begin{cases} \text{DYNAMIC\_DAG\_CONCURRENT}, & \text{if } S(T) \ge \theta \\ \text{SINGLE\_AGENT\_MONOLITH}, & \text{if } S(T) < \theta \end{cases}$$

where $\theta = 0.50$ by default.

---

## 5. Lossless Context Compactor

The compactor preserves four discrete layers of verified information:

1. **Active Invariants ($I$)**: Universal rules and execution constraints that cannot be modified by any node.
2. **Fact Registry ($F$)**: Key-value pairs verified through deterministic tool execution or environmental probes, annotated with source node ID and confidence.
3. **Artifact Delta Store ($A$)**: Filesystem and code modifications indexed by path, containing SHA-256 cryptographic hashes and unified diff hunks.
4. **Execution Trace Tail ($E$)**: Verbatim head (first 5 lines) and tail (last 25 lines) stdout/stderr buffers with targeted error snippet extraction.

### Retention Metric
$$R(C) = \frac{|F_{retained} \cap F_{ground\_truth}|}{|F_{ground\_truth}|}$$

TaskDAG maintains $R(C) = 1.00$ ($100\%$ factual retention) across task iterations.

---

## 6. Dynamic Replanning Mutation Algebra

When node $N_k$ fails at runtime:

1. **Remediation Node Injection ($\text{INJECT\_REMEDIATION}$)**:
   A diagnostic/remedial node $N_{rem}$ is created. All incoming edges to $N_k$ are duplicated to $N_{rem}$, and an edge $N_{rem} \to N_k$ is inserted. $N_k$ is reset to $\text{PENDING}$.
2. **Node Decomposition ($\text{SPLIT\_NODE}$)**:
   An overloaded node $N_k$ is partitioned into $N_{k,1}$ and $N_{k,2}$ with intermediate output contracts.
3. **Subtree Pruning ($\text{PRUNE\_SUBTREE}$)**:
   Downstream nodes whose preconditions depend on invalid states are marked $\text{PRUNED}$ to prevent wasted compute.
4. **Degradation to Monolith ($\text{DEGRADE\_TO\_MONOLITH}$)**:
   If repeated state divergences occur across concurrent branches, the DAG collapses into a single-agent linear sequence, eliminating the coordination tax.

All mutations preserve the directed acyclic invariant verified through Kahn's algorithm cycle detection prior to execution resumption.
