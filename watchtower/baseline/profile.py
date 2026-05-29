"""AgentProfile — per-agent behavioral baseline model."""
from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel


RESTRICTED_THRESHOLD = 50  # Minimum traces before unrestricted


class AgentProfile(BaseModel):
    agent_id: str
    trace_count: int            # number of traces used to build profile
    restricted_mode: bool       # True if trace_count < 50
    # Application level
    avg_step_count: float = 0.0
    std_step_count: float = 0.0
    avg_duration_ms: float = 0.0
    avg_cost: float = 0.0
    avg_tokens_in: float = 0.0
    avg_tokens_out: float = 0.0
    common_actions: list[str] = []   # top 5 actions by frequency
    # Memory level
    avg_write_count: float = 0.0
    last_updated: float = 0.0

    def model_post_init(self, __context) -> None:
        if self.last_updated == 0.0:
            self.last_updated = time.time()

    @property
    def is_new_agent(self) -> bool:
        return self.trace_count < RESTRICTED_THRESHOLD
