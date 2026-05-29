# SKILL: Layer 02 — Discovery

## Job
Find every agent. Active scan. No self-registration required.
Unknown agents flagged before they can emit signals.

## Files to create
- watchtower/discovery/scanner.py   — active scanner (polls known namespaces)
- watchtower/discovery/registry.py  — agent registry (dict-backed for POC)

## Registry interface
```python
class AgentRegistry:
    async def register(self, agent_id: str, metadata: dict) -> None: ...
    async def is_known(self, agent_id: str) -> bool: ...
    async def get_all(self) -> list[dict]: ...
    async def flag_unknown(self, agent_id: str) -> None: ...
    async def get_flagged(self) -> list[str]: ...
```

## Scanner interface
```python
class AgentScanner:
    async def scan(self) -> list[str]:
        """Returns list of discovered agent IDs not yet in registry."""
        ...
    async def run_continuous(self, interval_s: float = 30.0) -> None: ...
```

## Gate requirements (gate_02_discovery.py)
- Known agent registers successfully
- Unknown agent flagged when it tries to emit
- Discovery event written to output (dict with agent_id + flagged=True/False)
- is_known() returns False for unregistered agent
- Scanner finds agents in a test namespace
