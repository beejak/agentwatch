# SKILL: Layer 06 — Receiver

## Job
Consume signals from Redis queue.
Verify signal origin (HMAC) on EVERY emission — not just first contact.
Unverified signals dropped. Never reach Chronicle.

## Files to create
- watchtower/receiver/receiver.py       — Redis consumer
- watchtower/receiver/verification.py   — HMAC origin verification

## HMAC verification
- Each agent has a shared secret (from Access Graph manifest)
- Signal carries HMAC-SHA256(signal_json, agent_secret)
- Receiver verifies on every consume
- Tampering = any field changed after signing → verification fails

## SignalVerifier interface
```python
class SignalVerifier:
    async def sign(self, signal: Signal, secret: str) -> str: ...
    async def verify(self, signal: Signal, hmac_value: str, secret: str) -> bool: ...
```

## Receiver interface
```python
class SignalReceiver:
    async def start(self) -> None:
        """Consume from wt:signals stream continuously."""
        ...
    async def stop(self) -> None: ...
    # Verified signals forwarded to Chronicle
    # Rejected signals logged without writing to Chronicle
```

## Gate requirements (gate_06_receiver.py)
- Valid signed signal accepted and forwarded
- Signal with wrong HMAC rejected and dropped
- Signal with tampered field (modified after signing) rejected
- Rejection event logged (separate from Chronicle)
- Receiver processes at least 10 signals/second in test
