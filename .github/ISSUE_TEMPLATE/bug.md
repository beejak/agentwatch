---
name: Bug report
about: Detection missed, false positive, or system error
title: '[BUG] '
labels: bug
assignees: ''
---

## What happened

<!-- Describe the bug clearly -->

## Expected behavior

<!-- What should have happened -->

## Layer

<!-- Which layer is affected? Check all that apply -->
- [ ] 01 Core (signal shape)
- [ ] 02 Discovery
- [ ] 03 Access Graph
- [ ] 04 Policy Engine
- [ ] 05 Content Inspection
- [ ] 06 Receiver / HMAC
- [ ] 07 Memory Integrity Monitor
- [ ] 08 Chronicle
- [ ] 09 Verdict Engine
- [ ] 10 Behavioral Baseline
- [ ] 11 Coordination Signatures
- [ ] 12 Analyst (SC1/SC2/SC3)
- [ ] 13 Interceptor
- [ ] 15 FastAPI
- [ ] 16 Host Telemetry
- [ ] Infrastructure (Redis/ClickHouse/Postgres/Neo4j)

## Reproduction

```bash
# Minimal reproduction steps
```

## Gate test output

```
# Paste output of: make gate-NN
```

## Environment

- OS:
- Python:
- Docker Compose version:
- AgentWatch version / commit:
