---
name: False positive
about: AgentWatch flagged something that was legitimate behavior
title: '[FALSE POSITIVE] '
labels: false-positive
assignees: ''
---

## What was incorrectly flagged

<!-- Describe the agent behavior that was flagged -->

## Detection that fired

- [ ] Silent failure (SC2) — `infinite_retry_loop` / `token_burn` / `entropy_collapse`
- [ ] Coordination failure (SC1) — MAST signature: ___________
- [ ] Cross-layer discrepancy (SC3)
- [ ] Memory injection (MINJA)
- [ ] SpAIware (cross-session repeat)
- [ ] Content inspection pattern: ___________
- [ ] Policy engine denial
- [ ] Behavioral baseline deviation
- [ ] Other: ___________

## Why it's legitimate

<!-- Why should this behavior NOT be flagged? -->

## Trace details

```json
{
  "trace_id": "",
  "agent_id": "",
  "span_count": 0,
  "cost_anomaly_ratio": 0.0
}
```

## Suggested threshold adjustment

<!-- What threshold would prevent this false positive without missing real failures? -->
