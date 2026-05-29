# WatchTower

## Read First
SPEC.md — master spec. All layers, interfaces, invariants, tasks.
Run: /ck:build to execute next TODO task in §T.

## Commands (always use make — never raw invocations)
make layer-NN        → implement layer NN per SPEC.md §T
make gate-NN         → run gate test for layer NN
make gate-all        → run all gates in order, stop on fail
make poc             → run both proof scenarios
make test            → full suite
make progress        → show PROGRESS.md
make infra-status    → docker compose ps

## Proof Questions (both must pass in gate_14)
Q1: Coordination failure → identify agent, action, call tree position
Q2: MINJA memory poison via query-only → MIM detects before next trace

## Infra (already running)
Redis :6379 | ClickHouse :8123 | Postgres :5432 db=watchtower user=wt pass=wt | Neo4j :7687 user=neo4j pass=watchtower | Langfuse :3000

## Non-negotiable
1. Gate passes → update §T status in SPEC.md (TODO→DONE)
2. Test failure → add to §B in SPEC.md, fix, remove from §B when resolved
3. Caveman output. No prose unless asked.
4. Read SKILL.md in working directory before implementing any layer.
5. conftest.py wires all infra. Import fixtures, never create connections manually.
6. Signal shape defined ONCE in watchtower/core/signal.py. Never duplicate.
7. Chronicle is append-only. No UPDATE. No DELETE. Ever.
8. All I/O is async. No sync calls.
