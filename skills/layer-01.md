# SKILL: Layer 01 — Core

## Job
Define Signal, Trace, Span, and Event primitives. Foundation for all other layers.

## Files to create
- watchtower/core/signal.py  — Signal dataclass with ALL fields
- watchtower/core/trace.py   — Trace and Span primitives
- watchtower/core/events.py  — EventType enum

## Signal (canonical — define ONCE here, never duplicate)
```python
from pydantic import BaseModel, Field
from typing import Optional
import hashlib, json, time, uuid

class Signal(BaseModel):
    trace_id:         str
    span_id:          str
    parent_span_id:   Optional[str] = None
    agent_id:         str
    action:           str           # "llm_call","tool_use","handoff","delegate","query","memory_write"
    status:           str           # "ok","error","timeout","running"
    timestamp:        float         = Field(default_factory=time.time)
    duration_ms:      float         = 0.0
    tokens_in:        int           = 0
    tokens_out:       int           = 0
    model:            Optional[str] = None
    cost:             float         = 0.0
    instruction_hash: Optional[str] = None  # sha256 of inter-agent instructions
    caller_agent_id:  Optional[str] = None  # who called this agent
    process_guid:     Optional[str] = None  # Sysmon process GUID link
    retrieval_flag:   bool          = False  # was external data retrieved?
    memory_op:        Optional[str] = None  # "read","write","none"
    framework_fault:  bool          = False  # API/infra error
    policy_checked:   bool          = False  # PE ran on this action
    summary:          str           = ""    # truncated input/output

    @classmethod
    def create(cls, agent_id: str, action: str, **kwargs) -> "Signal":
        return cls(
            trace_id=kwargs.pop("trace_id", str(uuid.uuid4())),
            span_id=str(uuid.uuid4()),
            agent_id=agent_id,
            action=action,
            **kwargs
        )

    def compute_instruction_hash(self, instruction: str) -> str:
        return hashlib.sha256(instruction.encode()).hexdigest()
```

## Gate requirements (gate_01_core.py)
- Signal serialises to dict and back without data loss
- All fields present with correct types
- instruction_hash computed correctly from SHA256
- Signal.create() factory works
- EventType enum has all required values
