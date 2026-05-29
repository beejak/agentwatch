"""Temporal constraint types for the policy engine."""
from __future__ import annotations

import time
from enum import Enum

from pydantic import BaseModel


class ConstraintType(Enum):
    BEFORE = "before"   # A must happen before B
    AFTER = "after"     # A must happen after B
    FORALL = "forall"   # condition must hold for all actions
    EXISTS = "exists"   # condition must hold for at least one action


class TemporalConstraint(BaseModel):
    type: ConstraintType
    action_a: str
    action_b: str
    reason: str


class PolicyDecision(BaseModel):
    agent_id: str
    action: str
    permitted: bool
    reason: str
    timestamp: float = 0.0

    def model_post_init(self, __context) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()
