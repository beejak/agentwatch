§G WATCHTOWER
Agent observability system. 16 layers. Sequential build. Gate-first.
Three proof scenarios: SC1 (coord failure), SC2 (silent failure), SC3 (cross-layer discrepancy).

§C CONSTRAINTS
- Python 3.12 + FastAPI + asyncio. No sync I/O.
- Pydantic v2 models for all data structures.
- Signal shape defined ONCE in watchtower/core/signal.py. Never duplicate.
- Gate must pass before next layer starts. No exceptions.
- All commands via Makefile. Never raw pytest invocations.
- Caveman output only. No prose explanations unless asked.
- Chronicle: append-only. No UPDATE. No DELETE. Ever.

§I INTERFACES
signal_channel  | Redis stream    | key=wt:signals
chronicle_write | ClickHouse HTTP | db=watchtower, table=agent_spans
access_graph    | Neo4j bolt      | bolt://localhost:7687
baseline_store  | PostgreSQL      | db=watchtower, schema=baseline
policy_store    | PostgreSQL      | db=watchtower, schema=policy
mem_monitor     | Redis pub/sub   | channel=wt:memory_events
interceptor_bus | Redis stream    | key=wt:interceptor
langfuse        | HTTP            | http://localhost:3000

§V INVARIANTS
- Chronicle: append-only. No UPDATE. No DELETE. Ever.
- Signal origin: verified by Receiver on every emission, not just first.
- Verdict: score+source+reason. All three. Always.
- Interceptor: every action logged to Chronicle. Never silent.
- Policy Engine: default-deny. Must be permitted, not just not forbidden.
- New agent: restricted mode until 50 traces in baseline.
- Memory writes: all intercepted by MIM before Chronicle.
- LLM Judge: receives Trace Summariser output, never raw trace.

§T TASKS
| #  | Layer                    | Files                                              | Gate                  | Status |
|----|--------------------------|----------------------------------------------------|-----------------------|--------|
| 01 | Core                     | core/signal.py,core/trace.py,core/events.py        | gate_01_core          | DONE   |
| 02 | Discovery                | discovery/scanner.py,discovery/registry.py         | gate_02_discovery     | DONE   |
| 03 | Access Graph             | access_graph/graph.py,access_graph/manifest.py     | gate_03_access        | DONE   |
| 04 | Policy Engine            | policy_engine/engine.py,policy_engine/temporal.py  | gate_04_policy        | DONE   |
| 05 | Content Inspection       | content_inspection/inspector.py,patterns/          | gate_05_content       | DONE   |
| 06 | Receiver                 | receiver/receiver.py,receiver/verification.py      | gate_06_receiver      | DONE   |
| 07 | Memory Integrity Monitor | memory_monitor/monitor.py,memory_monitor/detectors/| gate_07_mim           | DONE   |
| 08 | Chronicle                | chronicle/writer.py,chronicle/schema.sql           | gate_08_chronicle     | DONE   |
| 09 | Verdict Engine           | verdict/engine.py,verdict/sources/,verdict/summariser.py | gate_09_verdict | DONE   |
| 10 | Behavioral Baseline      | baseline/engine.py,baseline/profile.py             | gate_10_baseline      | DONE   |
| 11 | Coordination Signatures  | coord_sigs/library.py,coord_sigs/signatures/       | gate_11_coord         | DONE   |
| 12 | Analyst                  | analyst/manager.py,analyst/attribution.py          | gate_12_analyst       | DONE   |
| 13 | Interceptor              | interceptor/interceptor.py,interceptor/quarantine.py| gate_13_interceptor  | DONE   |
| 14 | Integration + POC        | tests/poc/scenario_01.py,tests/poc/scenario_02.py  | gate_14_poc           | DONE   |
| 15 | FastAPI                  | api/main.py,api/routers/,api/schemas/              | gate_15_api           | DONE   |
| 16 | Host Telemetry Stub      | host_telemetry/sysmon.py,host_telemetry/falco.py   | gate_16_telemetry     | DONE   |

§B BUGS
| # | Layer | Symptom | Fix | Status |
|---|-------|---------|-----|--------|
| 1 | 06 Receiver | orchestrator.rpush (LIST) vs receiver.xread (STREAM) — pipeline dead | orchestrator.emit uses xadd | FIXED |
| 2 | 06 Receiver | HMAC field `_hmac` in payload, receiver reads `hmac` — always empty | emit uses `{"signal":..,"hmac":..}` xadd fields; signing uses Signal.model_dump() both sides | FIXED |
