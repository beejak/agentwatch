# Social Share Copy — WatchTower (Observation-First Forensics)

Paper: `paper/observability.pdf` — *WatchTower: Observation-First Forensics for Multi-Agent AI Systems*
Author: Rohit Jinsiwale
Code + data: github.com/beejak/agentwatch

All figures below come from the frozen eval artifacts in the repo (`eval/results/`), on
held-out splits with 2,000-sample bootstrap confidence intervals. Nothing here is rounded up.

---

## LinkedIn Post

**WatchTower: measuring whether multi-agent AI systems actually do what they report.**

The premise I set out to test empirically: an agent's self-report of success is not ground truth. On our corpus, a baseline that trusts agent self-reports achieves **0.00 recall** on silent failures — and that's structural, not a tuning problem. The agent that failed is the one authoring its own success message.

WatchTower is observation-first forensics. Instead of trusting the agent's narrative, it reconstructs execution from the layers underneath — distributed spans, token-cost curves, tool-call topology, host events — and flags the discrepancies the agent can't observe.

Evaluation — held-out splits, 2,000-sample bootstrap CIs; corpora and harness are in the repo:

**SC2 — silent-failure detection** (agent claims success; output is empty / wrong / truncated)
• Synthetic, n=269: recall **0.86** [0.78–0.93], precision 0.85, FPR 0.07
• Real traffic, n=120 (a live LLM agent captured behind an HTTP proxy): recall **1.00**, precision 1.00
• Baselines: self-report **0.00** recall; naive cost-threshold 0.27 recall

**SC3 — cross-layer discrepancy** (agent's logged outcome vs. the system's actual effect)
• recall **1.00** [1.00–1.00], precision 1.00; self-report baseline 0.00

**Overhead** — 380 traces / 5,171 spans, single CPU core, no GPU
• per-trace p99: SC2 0.035 ms, SC3 0.019 ms, SC1 0.224 ms
• 66,647 spans/sec — fast enough to run inline, not just offline

Stated limitations (in the paper, not buried): SC1 causal-root attribution is ≈0.5 on cascade cases — it attributes to the first error span, not the true root — and each detector has a quantified operating envelope (SC2 retry-loop detection engages at loop length ≥10; SC3 at an outcome delta ≥1).

Targeting peer review. Paper, code, and the frozen evaluation data: github.com/beejak/agentwatch

— Rohit Jinsiwale

---

## Short LinkedIn Caption (for sharing the paper link)

An AI agent's "task complete" is the suspect's own statement — not evidence.

We measured what that statement is worth: a baseline trusting agents' self-reports caught **0%** of silent failures. WatchTower reconstructs what actually happened from the layers underneath the agent and catches **0.86–1.00** of the same failures — sub-millisecond per trace, no GPU. Held-out data, bootstrap confidence intervals, limitations and all, in the repo.

New paper: *WatchTower — Observation-First Forensics for Multi-Agent AI Systems.*

github.com/beejak/agentwatch

#AIAgents #LLMObservability #MultiAgentSystems #AIReliability #LLMOps #AIEngineering

---

## X / Twitter Thread

**1/** Your AI agent reports "task complete." We measured what that report is actually worth. A baseline that trusts agents' self-reports caught 0.00 of silent failures in our corpus. Zero. The agent that failed is the one writing the success message.

**2/** WatchTower's premise: a self-report is not ground truth. So don't ask the agent how it went — reconstruct what actually happened from the layers underneath (spans, costs, tool calls, host events) and find the discrepancies it can't see.

**3/** Silent-failure detection (claims success, output is wrong/empty/truncated):
• 0.86 recall on synthetic traces (n=269)
• 1.00 on a real-traffic corpus — a live LLM agent behind a proxy (n=120)
• self-report baseline: 0.00 on both

**4/** Cross-layer discrepancy (what the agent logged vs. what the system did): 1.00 recall. Self-report: 0.00. And it runs inline — sub-ms per trace, ~66k spans/sec, one CPU core, no GPU.

**5/** Honest about the edges: causal-root attribution in deep cascades is still weak (~0.5 — blames the first error, not the true root), and each detector has an envelope below which it stays quiet. Corpora, baselines, limits all in the repo.

**6/** Paper + code (held-out splits, bootstrap CIs, frozen corpora): github.com/beejak/agentwatch
