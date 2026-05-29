"""Gate 04: Policy Engine — pre-execution verification with temporal constraints."""
import pytest

from watchtower.policy_engine.engine import PolicyEngine
from watchtower.policy_engine.temporal import ConstraintType, TemporalConstraint


@pytest.fixture
async def engine():
    e = PolicyEngine()
    # Allow a set of actions for test-agent
    await e.allow("test-agent", ["llm_call", "tool_use", "verify", "write", "auth", "api_call"])
    yield e


async def test_permitted_action(engine):
    decision = await engine.check("test-agent", "llm_call")
    assert decision.permitted is True
    assert decision.reason != ""


async def test_forbidden_action_default_deny(engine):
    decision = await engine.check("test-agent", "forbidden_action")
    assert decision.permitted is False
    assert decision.reason != ""


async def test_unknown_agent_default_deny(engine):
    decision = await engine.check("unknown-agent", "llm_call")
    assert decision.permitted is False


async def test_decision_has_reason(engine):
    d1 = await engine.check("test-agent", "llm_call")
    d2 = await engine.check("test-agent", "forbidden_action")
    assert d1.reason
    assert d2.reason


async def test_before_constraint_denied_when_prereq_missing(engine):
    """BEFORE(verify, write): write denied if verify not in history."""
    constraint = TemporalConstraint(
        type=ConstraintType.BEFORE,
        action_a="verify",
        action_b="write",
        reason="must verify before writing",
    )
    await engine.add_constraint("test-agent", constraint)

    # Attempt write without having done verify
    decision = await engine.check("test-agent", "write")
    assert decision.permitted is False
    assert "verify" in decision.reason.lower() or "before" in decision.reason.lower()


async def test_before_constraint_allowed_when_prereq_done(engine):
    """BEFORE(verify, write): write allowed after verify is recorded."""
    constraint = TemporalConstraint(
        type=ConstraintType.BEFORE,
        action_a="verify",
        action_b="write",
        reason="must verify before writing",
    )
    await engine.add_constraint("test-agent", constraint)
    await engine.record_action("test-agent", "verify")

    decision = await engine.check("test-agent", "write")
    assert decision.permitted is True


async def test_after_constraint_denied_before_prereq(engine):
    """AFTER(auth, api_call): api_call denied before auth."""
    constraint = TemporalConstraint(
        type=ConstraintType.AFTER,
        action_a="auth",
        action_b="api_call",
        reason="must authenticate before calling API",
    )
    await engine.add_constraint("test-agent", constraint)

    # No auth in history yet
    decision = await engine.check("test-agent", "api_call")
    assert decision.permitted is False


async def test_after_constraint_allowed_after_prereq(engine):
    """AFTER(auth, api_call): api_call allowed after auth recorded."""
    constraint = TemporalConstraint(
        type=ConstraintType.AFTER,
        action_a="auth",
        action_b="api_call",
        reason="must authenticate before calling API",
    )
    await engine.add_constraint("test-agent", constraint)
    await engine.record_action("test-agent", "auth")

    decision = await engine.check("test-agent", "api_call")
    assert decision.permitted is True


async def test_get_constraints(engine):
    constraint = TemporalConstraint(
        type=ConstraintType.BEFORE,
        action_a="a",
        action_b="b",
        reason="test",
    )
    await engine.add_constraint("test-agent", constraint)
    constraints = await engine.get_constraints("test-agent")
    assert any(c.action_a == "a" and c.action_b == "b" for c in constraints)


async def test_decision_has_timestamp(engine):
    decision = await engine.check("test-agent", "llm_call")
    assert decision.timestamp > 0
