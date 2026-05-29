"""Policy Engine — pre-execution verification with default-deny."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from watchtower.policy_engine.temporal import (
    ConstraintType,
    PolicyDecision,
    TemporalConstraint,
)


class PolicyEngine:
    """
    Pre-execution policy check. Default-deny.

    Each agent has:
      - A set of explicitly allowed actions (whitelist)
      - A list of temporal constraints that further restrict ordering
      - A history of actions already executed (per agent, per context/trace)
    """

    def __init__(self) -> None:
        self._allowed: dict[str, set[str]] = {}      # agent_id -> allowed actions
        self._constraints: dict[str, list[TemporalConstraint]] = {}
        self._history: dict[str, list[str]] = {}     # agent_id -> [action, ...]
        self._lock = asyncio.Lock()

    async def allow(self, agent_id: str, actions: list[str]) -> None:
        """Explicitly whitelist actions for an agent."""
        async with self._lock:
            existing = self._allowed.get(agent_id, set())
            self._allowed[agent_id] = existing | set(actions)

    async def record_action(self, agent_id: str, action: str) -> None:
        """Record that an action has been executed (update history)."""
        async with self._lock:
            history = self._history.setdefault(agent_id, [])
            history.append(action)

    async def check(self, agent_id: str, action: str, context: dict | None = None) -> PolicyDecision:
        """Check if an agent is allowed to perform an action. Default-deny."""
        context = context or {}

        async with self._lock:
            allowed = self._allowed.get(agent_id, set())
            constraints = list(self._constraints.get(agent_id, []))
            history = list(self._history.get(agent_id, []))

        # Default-deny: not in whitelist
        if action not in allowed:
            return PolicyDecision(
                agent_id=agent_id,
                action=action,
                permitted=False,
                reason=f"action '{action}' not in allowed list for agent '{agent_id}'",
                timestamp=time.time(),
            )

        # Check temporal constraints
        for constraint in constraints:
            decision = self._check_constraint(agent_id, action, constraint, history, context)
            if decision is not None:
                return decision

        return PolicyDecision(
            agent_id=agent_id,
            action=action,
            permitted=True,
            reason=f"action '{action}' permitted for agent '{agent_id}'",
            timestamp=time.time(),
        )

    def _check_constraint(
        self,
        agent_id: str,
        action: str,
        constraint: TemporalConstraint,
        history: list[str],
        context: dict,
    ) -> PolicyDecision | None:
        """
        Returns a deny PolicyDecision if the constraint is violated, else None.
        """
        ct = constraint.type

        if ct == ConstraintType.BEFORE:
            # action_a must happen before action_b
            # i.e., if we're trying to do action_b, action_a must be in history
            if action == constraint.action_b:
                if constraint.action_a not in history:
                    return PolicyDecision(
                        agent_id=agent_id,
                        action=action,
                        permitted=False,
                        reason=(
                            f"BEFORE constraint violated: '{constraint.action_a}' must "
                            f"occur before '{constraint.action_b}' — {constraint.reason}"
                        ),
                        timestamp=time.time(),
                    )

        elif ct == ConstraintType.AFTER:
            # action_b must happen after action_a
            # i.e., action_b is only allowed if action_a already happened
            if action == constraint.action_b:
                if constraint.action_a not in history:
                    return PolicyDecision(
                        agent_id=agent_id,
                        action=action,
                        permitted=False,
                        reason=(
                            f"AFTER constraint violated: '{constraint.action_b}' must "
                            f"come after '{constraint.action_a}' — {constraint.reason}"
                        ),
                        timestamp=time.time(),
                    )

        # FORALL and EXISTS are evaluated at trace-end, not pre-execution
        return None

    async def add_constraint(self, agent_id: str, constraint: TemporalConstraint) -> None:
        """Add a temporal constraint for an agent."""
        async with self._lock:
            constraints = self._constraints.setdefault(agent_id, [])
            constraints.append(constraint)

    async def get_constraints(self, agent_id: str) -> list[TemporalConstraint]:
        """Return all temporal constraints for an agent."""
        async with self._lock:
            return list(self._constraints.get(agent_id, []))
