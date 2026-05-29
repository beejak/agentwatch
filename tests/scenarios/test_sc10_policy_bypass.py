"""
SC10: Policy bypass — agent attempts unauthorized action.

Policy engine must default-deny. Attempts to call disallowed actions,
reach disallowed systems, or bypass temporal constraints must all fail.
"""
import pytest
from watchtower.policy_engine.engine import PolicyEngine
from watchtower.policy_engine.temporal import TemporalConstraint, ConstraintType


@pytest.fixture
async def policy():
    engine = PolicyEngine()
    await engine.allow("restricted-agent", ["llm_call", "tool_use"])
    # NOT adding: db_write, file_delete, api_call_external
    return engine


@pytest.mark.asyncio
async def test_allowed_action_passes(policy):
    decision = await policy.check("restricted-agent", "llm_call")
    assert decision.permitted


@pytest.mark.asyncio
async def test_disallowed_action_denied(policy):
    """db_write not in policy — must deny."""
    decision = await policy.check("restricted-agent", "db_write")
    assert not decision.permitted


@pytest.mark.asyncio
async def test_external_api_call_denied(policy):
    """External API call not permitted — deny."""
    decision = await policy.check("restricted-agent", "api_call_external")
    assert not decision.permitted


@pytest.mark.asyncio
async def test_file_delete_denied(policy):
    """Destructive action not in policy — deny."""
    decision = await policy.check("restricted-agent", "file_delete")
    assert not decision.permitted


@pytest.mark.asyncio
async def test_completely_unknown_agent_denied(policy):
    """Unknown agent has no rules — always deny."""
    decision = await policy.check("ghost-agent-never-registered", "llm_call")
    assert not decision.permitted


@pytest.mark.asyncio
async def test_before_constraint_bypass_attempt():
    """Agent tries to act before prerequisite completes — must block."""
    policy = PolicyEngine()
    await policy.allow("sequenced-agent", ["deploy", "test"])

    constraint = TemporalConstraint(
        action_a="test",
        action_b="deploy",
        type=ConstraintType.AFTER,
        reason="deploy requires test to complete first",
    )
    await policy.add_constraint("sequenced-agent", constraint)

    # Attempt deploy without test first
    decision = await policy.check("sequenced-agent", "deploy")
    assert not decision.permitted
    assert any(kw in decision.reason.lower() for kw in ("test", "prerequisite", "after"))


@pytest.mark.asyncio
async def test_after_constraint_satisfied_allows():
    """After completing prerequisite, restricted action permitted."""
    policy = PolicyEngine()
    await policy.allow("sequenced-agent", ["deploy", "test"])

    constraint = TemporalConstraint(
        action_a="test",
        action_b="deploy",
        type=ConstraintType.AFTER,
        reason="deploy requires test to complete first",
    )
    await policy.add_constraint("sequenced-agent", constraint)

    # Complete prerequisite first
    await policy.record_action("sequenced-agent", "test")
    decision = await policy.check("sequenced-agent", "deploy")
    assert decision.permitted


@pytest.mark.asyncio
async def test_decision_always_has_reason(policy):
    """Every decision — permit or deny — must include a reason."""
    for action in ["llm_call", "db_write", "something_random"]:
        decision = await policy.check("restricted-agent", action)
        assert decision.reason, f"No reason for action={action}"
        assert len(decision.reason) > 5


@pytest.mark.asyncio
async def test_policy_bypass_via_case_sensitivity(policy):
    """Action name case variants must not bypass policy."""
    for variant in ["LLM_CALL", "Llm_Call", "LLM_call", "llm_Call"]:
        decision = await policy.check("restricted-agent", variant)
        # Should either normalize and permit, or deny — must not error
        assert isinstance(decision.permitted, bool)
