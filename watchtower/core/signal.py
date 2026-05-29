"""
Signal — canonical shape for all agent observability events.
Defined ONCE here. Never duplicated elsewhere.
"""
from pydantic import BaseModel, Field
from typing import Optional
import hashlib
import uuid
import time


class Signal(BaseModel):
    trace_id:         str
    span_id:          str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id:   Optional[str] = None
    agent_id:         str
    action:           str
    status:           str = "ok"
    timestamp:        float = Field(default_factory=time.time)
    duration_ms:      float = 0.0
    tokens_in:        int = 0
    tokens_out:       int = 0
    model:            Optional[str] = None
    cost:             float = 0.0
    instruction_hash: Optional[str] = None
    caller_agent_id:  Optional[str] = None
    process_guid:     Optional[str] = None
    retrieval_flag:   bool = False
    memory_op:        Optional[str] = None
    framework_fault:  bool = False
    policy_checked:   bool = False
    summary:          str = ""

    @classmethod
    def create(cls, agent_id: str, action: str, **kwargs) -> "Signal":
        return cls(
            trace_id=kwargs.pop("trace_id", str(uuid.uuid4())),
            agent_id=agent_id,
            action=action,
            **kwargs
        )

    def compute_instruction_hash(self, instruction: str) -> str:
        return hashlib.sha256(instruction.encode()).hexdigest()

    def set_instruction_hash(self, instruction: str) -> None:
        self.instruction_hash = self.compute_instruction_hash(instruction)
