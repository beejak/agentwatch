"""Gate 03: Access Graph — permission checking and blast radius."""
import pytest

from watchtower.access_graph.manifest import AgentManifest
from watchtower.access_graph.graph import AccessGraph


@pytest.fixture
async def graph():
    g = AccessGraph()
    yield g


@pytest.fixture
def orchestrator_manifest():
    return AgentManifest(
        agent_id="orchestrator",
        allowed_actions=["llm_call", "handoff", "delegate"],
        allowed_systems=["redis"],
        allowed_callers=[],
        allowed_callees=["worker-a", "worker-b"],
        memory_scope="read_write",
        data_access=["logs", "configs"],
        blast_radius=[],
    )


@pytest.fixture
def worker_a_manifest():
    return AgentManifest(
        agent_id="worker-a",
        allowed_actions=["llm_call", "tool_use"],
        allowed_systems=["postgres"],
        allowed_callers=["orchestrator"],
        allowed_callees=[],
        memory_scope="read_only",
        data_access=["logs"],
        blast_radius=[],
    )


async def test_manifest_loads(graph, orchestrator_manifest):
    await graph.load_manifest(orchestrator_manifest)
    radius = await graph.get_blast_radius("orchestrator")
    assert isinstance(radius, list)


async def test_check_action_allowed(graph, orchestrator_manifest):
    await graph.load_manifest(orchestrator_manifest)
    assert await graph.check_action("orchestrator", "llm_call") is True
    assert await graph.check_action("orchestrator", "handoff") is True


async def test_check_action_disallowed(graph, orchestrator_manifest):
    await graph.load_manifest(orchestrator_manifest)
    assert await graph.check_action("orchestrator", "forbidden_action") is False


async def test_check_action_unknown_agent(graph):
    assert await graph.check_action("ghost-agent", "llm_call") is False


async def test_check_caller_allowed(graph, orchestrator_manifest, worker_a_manifest):
    await graph.load_manifest(orchestrator_manifest)
    await graph.load_manifest(worker_a_manifest)
    # orchestrator is in worker-a's allowed_callers
    assert await graph.check_caller("orchestrator", "worker-a") is True


async def test_check_caller_disallowed(graph, orchestrator_manifest, worker_a_manifest):
    await graph.load_manifest(orchestrator_manifest)
    await graph.load_manifest(worker_a_manifest)
    # worker-a cannot call orchestrator
    assert await graph.check_caller("worker-a", "orchestrator") is False


async def test_blast_radius_includes_systems(graph, orchestrator_manifest):
    await graph.load_manifest(orchestrator_manifest)
    radius = await graph.get_blast_radius("orchestrator")
    # orchestrator can access redis and its callees
    assert "redis" in radius or "worker-a" in radius


async def test_blast_radius_empty_for_unknown(graph):
    radius = await graph.get_blast_radius("unknown-agent-xyz")
    assert radius == []


async def test_zt_reverification(graph, orchestrator_manifest):
    """ZT: same check works consistently on repeated calls."""
    await graph.load_manifest(orchestrator_manifest)
    for _ in range(5):
        assert await graph.check_action("orchestrator", "llm_call") is True
        assert await graph.check_action("orchestrator", "forbidden") is False
