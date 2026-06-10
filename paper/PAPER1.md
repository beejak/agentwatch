# WatchTower: An Agent's Self-Report Is Not Ground Truth
## Trajectory- and Host-Level Forensics for Multi-Agent AI Systems

**Status:** DRAFT (Paper 1 — observability). Evidence in `eval/`; numbers below are
reproducible (`make test`, `make eval`, `python -m eval.sweep`, `make capture-tier1-llm`).
Enforcement is a companion system (Paper 2, `agentwatch-firewall`).

---

## Abstract

Monitoring tools for LLM-agent systems consume what the agent *reports* it did — the trace
of tool calls and outputs it emits. We show this is insufficient as a security signal:
agents fail in ways their self-report does not reveal, and a compromised or buggy agent can
under-report its own actions. We characterize two such structural blind spots — **silent
failures** (the agent reports success while looping, burning tokens, or collapsing) and
**cross-layer discrepancies** (the agent's reported actions disagree with an independent host
view) — and present **WatchTower**, an observation-first platform that detects them by
reconciling the agent's self-report against (a) the *shape* of its execution trajectory and
(b) an independent *host* ground truth. On a frozen, held-out corpus, a faithful self-report
baseline detects **0%** of both classes by construction, while WatchTower detects silent
failures at 0.86 recall / 0.07 FP and cross-layer discrepancies at 1.00 / 0.00. We confirm the
mechanism on **real, emergent traffic** from an LLM agent (DeepSeek) whose behavior is captured
through an egress proxy, and we map the detection envelope — including where detection falls
off. WatchTower observes and attributes; it does not enforce (a co-designed enforcement layer
is described separately).

---

## 1. Introduction

LLM agents increasingly act through tools, memory, and peer agents. Existing observability
(LangSmith, Langfuse) records the agent's emitted trace and surfaces it on a dashboard. That
trace is the agent's **self-report** — and a self-report is not ground truth:

- **The $47k failure (silent).** An agent retries the same call 150 times; every span is
  `status=ok`; cost balloons. Nothing *errored* — an output-level monitor shows a green
  dashboard while the task was broken the entire time.
- **The lying agent (cross-layer).** An agent's trace says it made one network call; the host
  observed four. The three unreported calls are invisible to anything that trusts the trace.

Both are *security* problems: the second is an exfiltration/tampering signal. We argue
monitoring must **reconcile the self-report against independent evidence** — the execution
trajectory's shape and an independent host view — and that discrepancy is the signal.

**Contributions.**
- **C1 — silent-failure detection (SC2):** cost-anomaly + retry-loop + entropy-collapse
  detectors that flag failures which never raise an error.
- **C2 — cross-layer reconciliation (SC3):** comparison of agent-reported network actions
  against host telemetry, scored as a tamper/exfil discrepancy.
- **C3 — an append-only forensic Chronicle + attribution (SC1):** a no-UPDATE/no-DELETE event
  store enabling post-hoc attribution of a coordination failure to agent, action, and
  call-tree position.
- **Evidence:** a frozen, held-out evaluation with baselines and confidence intervals, an
  operating-envelope sweep, and confirmation on real emergent LLM-agent traffic.

---

## 2. Background and Related Work

**Trace/output monitors (LangSmith, Langfuse).** Record and visualize the agent's emitted
trace. They trust the self-report: they cannot flag an all-`ok` silent failure, and have no
host concept to detect report-vs-reality gaps. WatchTower targets exactly these blind spots.

**The observability gap [2603.26942].** Argues output-level human feedback is insufficient for
coding agents — compliant-looking output can hide unsafe trajectories. We *operationalize* this
argument with concrete detectors and an evaluation.

**Agentic process observability [2505.20127].** Treats trajectories as process-mining targets;
notes stochasticity (same input → different trajectories). Complementary; not a security
discrepancy detector.

**Host EDR (Sysmon, Falco, eBPF).** Observe OS-level network/process events but have no agent
semantics. WatchTower *bridges* host events to the agent trajectory (SC3) via process GUIDs.

Positioning: the novelty is **multi-layer reconciliation (self-report ↔ trajectory ↔ host) as a
security signal**, with concrete detectors, a forensic substrate, and a held-out evaluation.

---

## 3. Threat and Failure Model

- Agents may report success while failing — non-adversarial bugs (retry storms, token burn)
  *and* adversarial masking.
- A compromised/injected agent (or a compromised tool it calls) may under-report network
  activity (SC3 exfil).
- **In scope:** detection, attribution, forensic record. **Out of scope (Paper 2):**
  enforcement/blocking, prompt-injection content classification, cross-session taint.

---

## 4. System Design

WatchTower is a passive, append-only, 16-layer side-car. Agents emit HMAC-signed `Signal`s to a
Redis stream; a Receiver verifies origin on every signal and fans out to inspection layers;
everything is recorded to an append-only **Chronicle** (ClickHouse, no UPDATE/DELETE, 90-day
TTL). Analyses run over the Chronicle. *(See `ARCHITECTURE.md` for the full data flow + the
mermaid diagrams in `README.md`.)*

- **SC1 attribution.** From a trace's spans, identify the failing agent/action and call-tree
  position, classified against a coordination-signature (MAST) library.
- **SC2 silent failure.** Over a trace's spans: a cost-anomaly ratio (actual/expected), a
  repeated-summary retry-loop test, and an entropy-collapse test — none of which require an
  error status.
- **SC3 cross-layer.** Count agent-reported network actions; count host `NetworkConnect` events
  for the same process GUIDs; a positive delta (host > reported) is the discrepancy.

A 3-stage verdict engine (deterministic → behavioral-baseline → sampled LLM judge) and a
behavioral baseline (per-agent 3σ; restricted mode until 50 traces) support the analyses.

---

## 5. Implementation

Python 3.12, all-async; Pydantic v2 (`Signal` defined once); FastAPI surface; ClickHouse
Chronicle; Redis transport; PostgreSQL baseline; Neo4j access graph; HMAC-SHA256 signing;
12-factor env config (`watchtower/config.py`). A lightweight SDK (`watchtower/emitter.py`) lets
any agent emit signed signals to the Chronicle or the `wt:signals` stream. ~16 layers, each
gated by a test (`make gate-all`). The LLM judge is a real OpenAI-compatible client when
configured, a deterministic heuristic otherwise.

---

## 6. Evaluation

Frozen, human-labeled corpora; held-out split; baselines head-to-head; bootstrap 95% CIs.
Reproduce: `make eval` (synthetic), `python -m eval.sweep` (envelope), `make capture-tier1-llm`
(real). Baselines: **B1** self-report (flags only an explicit `error` span — the faithful upper
bound of any self-report-trusting monitor) and **B2** naive cost threshold.

### 6.1 Held-out synthetic (n=269; 380-trace corpus)

| detector | SC2 recall | SC2 FPR | SC3 recall | SC3 FPR |
|----------|-----------:|--------:|-----------:|--------:|
| **WatchTower** | **0.86** | 0.07 | **1.00** | 0.00 |
| self-report (B1) | **0.00** | 0.00 | **0.00** | 0.00 |
| naive cost (B2) | 0.27 | 0.07 | — | — |

**H3 (the spine):** the self-report baseline has **0 recall** on both — it never sees the
signal. WatchTower also beats naive cost (loops/entropy catch what pure cost misses; pure cost
false-positives on expensive-but-correct work).

### 6.2 Operating envelope (where it holds AND falls off)

- SC2 silent-loop fires at **loop length ≥ 10** (shorter loops are missed — by threshold).
- SC2 token-burn fires at **total cost ≥ \$0.12**, and false-positives expensive-but-correct
  traces above that — a precision/recall trade-off, reported honestly.
- SC3 fires at **delta ≥ 1**; negative delta (host < reported, e.g. telemetry sampling) **never**
  fires (no false alarm).

### 6.3 Near-real-world (real LLM agent)

A DeepSeek agent (ReAct loop) acts against tasks; tools make real HTTP egress through an
independent proxy. SC2 (the model genuinely loops) and SC3 (a compromised tool's hidden egress)
**emerge** from the model's behavior. On the captured corpus (**n=120; 40/class**), WatchTower
detects SC2 and SC3 at **1.00** with **0.00** FP and the self-report baseline at **0.00** — H3
confirmed on real, emergent traffic. *(The 1.00 reflects a clean signal once the condition occurs; §6.1's 0.86 —
which includes borderline cases — is the conservative headline.)*

---

## 7. Discussion and Limitations

- **SC1 attribution is first-error, not causal-root.** On cascade failures where the root error
  is not the first error span, attribution mis-identifies the agent (envelope accuracy 0.5 on a
  single/cascade pair). Causal-root attribution is future work.
- **Synthetic realism.** The bulk corpus is generated; the robust result is the *baseline gap*
  (structural), confirmed on real LLM-agent traffic. Absolute numbers will move on production
  traffic.
- **SC3 without kernel telemetry** validates HTTP egress only (proxy). Raw-socket/DNS/proxy-bypass
  require an eBPF/Sysmon collector (bridge implemented, `eval/capture/ebpf_bridge.py`).
- **LLM judge is fallible** — it is the last, sampled verdict stage by design; deterministic
  stages are authoritative.

---

## 8. Conclusion

Treating the agent's self-report as untrusted — and reconciling it against the trajectory and an
independent host view — catches silent failures and report-vs-reality gaps that self-report-based
monitoring structurally cannot. We release the implementation, frozen corpora, and harness for
reproduction.

*Artifacts: `eval/corpus/*.jsonl`, `eval/results/*.json`, `examples/sample_output.json`,
`docs/TESTING.md`, `docs/REAL_TRAFFIC_VALIDATION.md`.*
