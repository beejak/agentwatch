"""Gate 13: Interceptor — halt, quarantine, revoke."""
import asyncio
import uuid
import pytest

from watchtower.interceptor.interceptor import Interceptor, InterceptorAction
from watchtower.access_graph.graph import AccessGraph
from watchtower.access_graph.manifest import AgentManifest


@pytest.fixture
async def access_graph():
    g = AccessGraph()
    # Load orchestrator that can reach worker-a
    await g.load_manifest(AgentManifest(
        agent_id="orchestrator",
        allowed_actions=["llm_call", "delegate"],
        allowed_systems=["redis"],
        allowed_callers=[],
        allowed_callees=["worker-a"],
        memory_scope="read_write",
        data_access=["logs"],
        blast_radius=[],
    ))
    return g


@pytest.fixture
def interceptor(access_graph):
    return Interceptor(access_graph=access_graph)


async def test_halt_writes_action(interceptor):
    action = await interceptor.halt("agent-x", "test halt", trigger="analyst")
    assert isinstance(action, InterceptorAction)
    assert action.action_type == "halt"
    assert action.target_agent == "agent-x"
    assert action.logged is True


async def test_quarantine_returns_blast_radius(interceptor):
    action = await interceptor.quarantine("orchestrator", "testing quarantine", trigger="analyst")
    assert action.action_type == "quarantine"
    assert isinstance(action.blast_radius, list)
    # orchestrator's blast radius should include worker-a and redis
    assert len(action.blast_radius) > 0


async def test_is_quarantined_after_quarantine(interceptor):
    await interceptor.quarantine("bad-agent", "test", trigger="policy_engine")
    assert await interceptor.is_quarantined("bad-agent") is True


async def test_is_not_quarantined_before(interceptor):
    assert await interceptor.is_quarantined("clean-agent") is False


async def test_revoke_memory_write(interceptor):
    action = await interceptor.revoke_memory_write("minja-agent", "MINJA detected")
    assert action.action_type == "revoke_memory"
    assert action.logged is True
    assert await interceptor.is_memory_write_revoked("minja-agent") is True


async def test_revoke_prevents_write(interceptor):
    """After revoke, MIM write should be blocked."""
    await interceptor.revoke_memory_write("poisoned-agent", "test")
    assert await interceptor.is_memory_write_revoked("poisoned-agent") is True
    # Clean agent not affected
    assert await interceptor.is_memory_write_revoked("clean-agent") is False


async def test_all_actions_logged(interceptor):
    """Every InterceptorAction must be in the action log."""
    await interceptor.halt("a1", "test", "analyst")
    await interceptor.quarantine("a2", "test", "mim")
    await interceptor.revoke_memory_write("a3", "test")

    actions = await interceptor.get_all_actions()
    assert len(actions) == 3
    for a in actions:
        assert a.logged is True


async def test_action_has_timestamp(interceptor):
    action = await interceptor.halt("agent-t", "test", "analyst")
    assert action.timestamp > 0
