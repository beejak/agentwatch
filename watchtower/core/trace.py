"""Trace and Span primitives."""
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import time


class Span(BaseModel):
    trace_id:      str
    span_id:       str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    agent_id:      str
    action:        str
    status:        str = "ok"
    timestamp:     float = Field(default_factory=time.time)
    duration_ms:   float = 0.0


class Trace(BaseModel):
    trace_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: float = Field(default_factory=time.time)
    ended_at:   Optional[float] = None
    spans:      list[Span] = Field(default_factory=list)

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    def close(self) -> None:
        self.ended_at = time.time()
