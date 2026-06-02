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
    trace_id:         str   = Field(max_length=128)
    span_id:          str   = Field(default_factory=lambda: str(uuid.uuid4()), max_length=128)
    parent_span_id:   Optional[str] = Field(default=None, max_length=128)
    agent_id:         str   = Field(max_length=256)
    action:           str   = Field(max_length=256)
    status:           str   = Field(default="ok", max_length=64)
    timestamp:        float = Field(default_factory=time.time)
    duration_ms:      float = 0.0
    tokens_in:        int   = 0
    tokens_out:       int   = 0
    model:            Optional[str] = Field(default=None, max_length=128)
    cost:             float = 0.0
    instruction_hash: Optional[str] = Field(default=None, max_length=64)
    caller_agent_id:  Optional[str] = Field(default=None, max_length=256)
    process_guid:     Optional[str] = Field(default=None, max_length=128)
    retrieval_flag:   bool  = False
    memory_op:        Optional[str] = Field(default=None, max_length=64)
    framework_fault:  bool  = False
    policy_checked:   bool  = False
    summary:          str   = Field(default="", max_length=8192)

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
