# Real-Traffic Validation Plan (SC2 / SC3)

Goal: validate the SC2 (silent failure) and SC3 (cross-layer discrepancy) claims on
**near-real-world** agent traffic, and present results honestly (limitations disclosed).
Two complementary modes; both produce **preserved, frozen** artifacts under `eval/`.

## Mode A — Network-traffic *simulation* (have, will formalize)
The frozen synthetic corpus (`eval/corpus/traces_v0.1.jsonl`) already simulates agent
network spans + host `NetworkConnect` events for SC3. This gives controlled, labeled,
reproducible coverage across the failure space (volume + edge cases). Tagged `source: synthetic`.

## Mode B — Near-real-world capture (to build)
Run **real LLM agents** and capture their **actual** behavior + an **independent** record of
their real network calls.

```
real agents (smolagents/LangGraph)  ──emit Signals (self-report)──►  capture → chronicle
        │  all outbound HTTP forced through ↓
        └──────────────►  mitmproxy (egress proxy)  ──►  independent network truth
```

- **Self-report:** instrument agent tools to emit `Signal`s (what the agent *says* it did).
- **Independent truth:** route all agent egress through **mitmproxy** (userspace, venv) →
  the proxy log is the host's independent view of *actual* outbound calls. No kernel module.
- **Inject SC3:** a tool that calls out **without** emitting a span (under-report / hidden
  exfil) → proxy sees it, agent doesn't report it → a real, detectable discrepancy.
- **Inject SC2:** a tool that loops / returns `pending` so a real agent genuinely spins, or a
  task it silently fails → real silent failure (status ok, cost balloons).
- **Labels:** derive from gradeable task outcomes (reported-success vs. actually-failed) —
  independent of WatchTower.
- **Freeze + report:** capture once → freeze into the corpus as `source: captured` → run
  detectors → report **per-source** metrics next to synthetic (answers "does it generalize
  beyond synthetic?").

### What's needed
`mitmproxy` (pip) · an agent framework (`smolagents`/LangGraph) · `LLM_API_KEY` (OpenAI-compatible)
· a task/tool harness · bridges: proxy-log → host-events, agent-tool → `Signal`.

### Limitations (disclose in the paper)
Skipping kernel telemetry means Mode B validates SC3 for **HTTP(S) egress only**. NOT covered:
non-HTTP/raw sockets, DNS exfil, and **proxy-bypass** (code that ignores `HTTP_PROXY`).
- Mitigation (userspace): force all egress through the proxy via a **network namespace +
  iptables REDIRECT**, so bypass attempts are caught/blocked — more setup, no kernel module.
- Full coverage (raw sockets / DNS / file / process) needs **eBPF or Sysmon on a real Linux
  host/VM** — a later upgrade, out of scope for the venv-local testbed.
- This is **"real agent traffic in a testbed," not production traffic.** True production
  validation = shadow-deploy (OTel exporter + egress proxy) in a live environment, with
  consent/privacy handling.

### Output
Captured corpus + per-source metrics preserved under `eval/` and `eval/results/`, tagged to a
git tag at capture time (reproducibility / paper provenance).
