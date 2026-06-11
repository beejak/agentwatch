# Social Share Copy — WatchTower (Observation-First Forensics)

Paper: `paper/observability.pdf` — *WatchTower: Observation-First Forensics for Multi-Agent AI Systems*
Author: Rohit Jinsiwale
Code + data: github.com/beejak/agentwatch

Every figure below comes from the frozen eval artifacts in the repo (`eval/results/`), on
held-out splits with 2,000-sample bootstrap confidence intervals. Nothing is rounded up.

This file holds three framings of the same announcement — a **non-technical** report, a
**technical** report, and the **merged report** (the one to actually post) that balances the
two — plus a short caption, an X thread, and the hashtag set.

---

## ⭐ Merged Report — primary LinkedIn post

**Your AI agent says it finished the task. Can you prove it?**

That question is the whole reason I built WatchTower. In a multi-agent system, when the agents report "done," that report is the *suspect's own statement* — and we measured exactly what it's worth. A baseline that trusts agents' self-reports caught **0%** of the silent failures in our corpus. Not "low" — zero. Which makes sense the moment you say it out loud: the agent that quietly failed is the same one writing the success message.

So WatchTower takes the opposite stance — **observation-first forensics.** Don't ask the agent how it went; reconstruct what actually happened from the layers underneath it (distributed spans, token-cost curves, tool-call topology, host events) and surface the discrepancies the agent can't see or won't admit.

What that buys you, on held-out data with confidence intervals:

- **Silent failures** — agent claims success, but the output is empty, wrong, or truncated: **0.86 recall** on synthetic traces (n=269) and **1.00** on a real-traffic corpus we captured by putting a live LLM agent behind an HTTP proxy (n=120). Self-report baseline on the same data: **0.00**.
- **Cross-layer discrepancies** — what the agent *logged* vs. what the system *actually did*: **1.00 recall**. Self-report: **0.00**.
- **Cheap enough to run inline:** sub-millisecond per trace, ~66,000 spans/sec on a single CPU core, no GPU.

And I'm just as upfront about the edges, because the point was to measure honestly, not to demo well: pinning the *causal root* of a deep failure cascade is still weak (≈0.5 — it blames the first error it sees, not the true origin), and each detector has an operating envelope below which it deliberately stays quiet. All of it — the corpora, the baselines, the blind spots — is in the repo and written into the paper.

If you're running agents anywhere near production, I'd genuinely value your read.

📄 Paper + 💻 code + frozen data: github.com/beejak/agentwatch

— Rohit Jinsiwale

#AIAgents #LLMObservability #MultiAgentSystems #AIReliability #AIEngineering #LLMOps #AISafety #AgentSecurity #MLOps #GenAI

---

## Non-Technical Report

**We built a lie detector for AI agents.**

AI "agents" are programs that carry out multi-step tasks on their own — booking, researching, writing code, calling other tools. The catch: when an agent finishes, the only thing most systems have to go on is the agent's *own* claim that it succeeded. That's like asking a suspect whether they did it and writing down "no."

We put that to the test. A monitor that simply trusts what agents report about themselves missed **100%** of the cases where an agent quietly failed but still said "done." It can't do better — the thing that failed is the thing filing the report.

WatchTower works differently. Instead of taking the agent's word, it watches what the system *actually does* underneath — every tool call, every cost, every action on the machine — and compares that to the story the agent tells. When the two don't match, it flags it.

The result: on the same failures the self-report monitor missed entirely, WatchTower catches the large majority — and in our real-traffic test, all of them — fast enough to run live, on an ordinary computer, with no special hardware. We're also honest about what it can't yet do well, and we've published all the test data so anyone can check.

The bigger idea: as we hand more real work to AI agents, "the agent said it worked" can't be the standard of proof. You need an independent observer. That's what this is.

💻 github.com/beejak/agentwatch

---

## Technical Report

**WatchTower: measuring whether multi-agent AI systems actually do what they report.**

Premise, tested empirically: an agent's self-report of success is not ground truth. On our corpus a self-report baseline achieves **0.00 recall** on silent failures — structural, not a tuning artifact: the failing agent authors its own success message.

WatchTower is observation-first forensics — it reconstructs execution from lower layers (distributed spans, token-cost curves, tool-call topology, host events) and detects discrepancies the agent cannot observe.

Evaluation — held-out splits, 2,000-sample bootstrap CIs; corpora + harness in repo:

**SC2 — silent-failure detection** (claims success; output empty / wrong / truncated)
- Synthetic, n=269: recall **0.86** [0.78–0.93], precision 0.85, FPR 0.07
- Real traffic, n=120 (live LLM agent captured behind an HTTP proxy): recall **1.00**, precision 1.00
- Baselines: self-report **0.00** recall; naive cost-threshold 0.27 recall

**SC3 — cross-layer discrepancy** (agent's logged outcome vs. actual system effect)
- recall **1.00** [1.00–1.00], precision 1.00; self-report baseline 0.00

**Overhead** — 380 traces / 5,171 spans, single CPU core, no GPU
- per-trace p99: SC2 0.035 ms, SC3 0.019 ms, SC1 0.224 ms
- 66,647 spans/sec — inline-deployable, not offline-only

**Stated limitations** (in the paper, not buried): SC1 causal-root attribution ≈0.5 on cascade cases (attributes to the first error span, not the true root); each detector has a quantified operating envelope (SC2 retry-loop detection engages at loop length ≥10; SC3 at an outcome delta ≥1).

Targeting peer review. Paper, code, frozen evaluation data: github.com/beejak/agentwatch

— Rohit Jinsiwale

---

## Short Caption (for sharing the paper link)

An AI agent's "task complete" is the suspect's own statement — not evidence.

We measured what that's worth: a baseline trusting agents' self-reports caught **0%** of silent failures. WatchTower reconstructs what actually happened from the layers underneath and catches **0.86–1.00** of the same failures — sub-millisecond per trace, no GPU. Held-out data, bootstrap CIs, limitations and all, in the repo.

New paper: *WatchTower — Observation-First Forensics for Multi-Agent AI Systems.*

github.com/beejak/agentwatch

#AIAgents #LLMObservability #MultiAgentSystems #AIReliability #LLMOps

---

## X / Twitter Thread

**1/** Your AI agent reports "task complete." We measured what that report is actually worth: a baseline that trusts agents' self-reports caught 0.00 of silent failures in our corpus. Zero. The agent that failed is the one writing the success message.

**2/** WatchTower's premise: a self-report is not ground truth. So don't ask the agent how it went — reconstruct what actually happened from the layers underneath (spans, costs, tool calls, host events) and find the discrepancies it can't see.

**3/** Silent-failure detection (claims success; output wrong/empty/truncated):
• 0.86 recall on synthetic traces (n=269)
• 1.00 on a real-traffic corpus — a live LLM agent behind a proxy (n=120)
• self-report baseline: 0.00 on both

**4/** Cross-layer discrepancy (what the agent logged vs. what the system did): 1.00 recall. Self-report: 0.00. And it runs inline — sub-ms per trace, ~66k spans/sec, one CPU core, no GPU.

**5/** Honest about the edges: causal-root attribution in deep cascades is still weak (~0.5 — blames the first error, not the true root), and each detector has an envelope below which it stays quiet. Corpora, baselines, limits all in the repo.

**6/** Paper + code (held-out splits, bootstrap CIs, frozen corpora): github.com/beejak/agentwatch

#AIAgents #LLMObservability #MultiAgentSystems #AIReliability #AISafety

---

## Hashtag Set (mix + match)

Core: `#AIAgents` `#LLMObservability` `#MultiAgentSystems` `#AIReliability` `#AIEngineering`
Reach: `#LLMOps` `#MLOps` `#GenAI` `#AISafety` `#AgentSecurity` `#ArtificialIntelligence`
