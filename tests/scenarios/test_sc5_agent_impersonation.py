"""
SC5: Agent impersonation — rogue agent claims to be trusted agent.

A malicious agent sets caller_agent_id to a trusted agent to bypass
access controls. Access graph + policy engine must catch this.
"""
import pytest
import uuid
from watchtower.access_graph.graph import AccessGraph
from watchtower.access_graph.manifest import AgentManifest
from watchtower.policy_engine.engine import PolicyEngine


@pytest.fixture
def graph():
    return AccessGraph()


@pytest.fixture
async def policy():
    engine = PolicyEngine()
    await engine.allow("trusted-agent", ["llm_call"])
    return engine


@pytest.fixture
def trusted_manifest():
    return AgentManifest(
        agent_id="trusted-orchestrator",
        allowed_actions=["delegate", "llm_call"],
        allowed_systems=["redis", "postgres"],
        allowed_callers=[],
        allowed_callees=["worker-a", "worker-b"],
        memory_scope="read_write",
        data_access=["logs"],
        blast_radius=[],
    )


@pytest.fixture
def worker_manifest():
    return AgentManifest(
        agent_id="worker-a",
        allowed_actions=["llm_call", "tool_use"],
        allowed_systems=["redis"],
        allowed_callers=["trusted-orchestrator"],  # Only trusted-orchestrator may call
        allowed_callees=[],
        memory_scope="read_only",
        data_access=["logs"],
        blast_radius=[],
    )


@pytest.mark.asyncio
async def test_rogue_agent_cannot_call_worker_directly(graph, trusted_manifest, worker_manifest):
    """Rogue agent claims orchestrator identity — access graph must reject."""
    await graph.load_manifest(trusted_manifest)
    await graph.load_manifest(worker_manifest)

    # Rogue agent is NOT registered — impersonates trusted-orchestrator
    allowed = await graph.check_caller("rogue-agent", "worker-a")
    assert not allowed, "Impersonation not caught: rogue-agent accessed worker-a"


@pytest.mark.asyncio
async def test_legitimate_caller_allowed(graph, trusted_manifest, worker_manifest):
    """Legitimate call from registered orchestrator must pass."""
    await graph.load_manifest(trusted_manifest)
    await graph.load_manifest(worker_manifest)
    allowed = await graph.check_caller("trusted-orchestrator", "worker-a")
    assert allowed


@pytest.mark.asyncio
async def test_unregistered_agent_default_deny(policy):
    """Unregistered agent must be denied regardless of action."""
    decision = await policy.check("unknown-rogue-agent", "llm_call")
    assert not decision.permitted


@pytest.mark.asyncio
async def test_caller_spoofing_detected_via_graph(graph, trusted_manifest, worker_manifest):
    """
    Rogue agent spoofs caller_agent_id in signal.
    Access graph independently verifies the actual caller — catches mismatch.
    """
    await graph.load_manifest(trusted_manifest)
    await graph.load_manifest(worker_manifest)

    # Signal claims caller=trusted-orchestrator, actual sender=rogue-agent
    actual_sender = "rogue-agent"
    claimed_caller = "trusted-orchestrator"

    # Graph check: is actual_sender registered and allowed to call worker-a?
    actual_allowed = await graph.check_caller(actual_sender, "worker-a")
    claimed_allowed = await graph.check_caller(claimed_caller, "worker-a")

    assert not actual_allowed   # rogue-agent blocked
    assert claimed_allowed      # trusted-orchestrator would be allowed (but it's not the actual sender)


@pytest.mark.asyncio
async def test_blast_radius_contains_impersonated_agent(graph, trusted_manifest, worker_manifest):
    """If trusted-orchestrator is quarantined, worker-a should be in blast radius."""
    await graph.load_manifest(trusted_manifest)
    await graph.load_manifest(worker_manifest)
    blast = await graph.get_blast_radius("trusted-orchestrator")
    assert "worker-a" in blast or "worker-b" in blast
