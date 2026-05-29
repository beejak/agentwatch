"""Gate 02: Discovery — agent registry and unknown agent detection."""
import pytest
import uuid



@pytest.fixture
async def registry():
    from watchtower.discovery.registry import AgentRegistry
    r = AgentRegistry()
    await r.start()
    yield r
    await r.stop()


async def test_register_agent(registry):
    agent_id = f"agent-{uuid.uuid4()}"
    await registry.register(agent_id, {"type": "worker"})
    assert await registry.is_known(agent_id)


async def test_unknown_agent_not_in_registry(registry):
    assert not await registry.is_known("totally-unknown-agent-xyz")


async def test_flag_unknown_agent(registry):
    unknown_id = f"shadow-{uuid.uuid4()}"
    await registry.flag_unknown(unknown_id)
    flagged = await registry.get_flagged()
    assert unknown_id in flagged


async def test_get_all_agents(registry):
    ids = [f"agent-{uuid.uuid4()}" for _ in range(3)]
    for aid in ids:
        await registry.register(aid, {})
    all_agents = await registry.get_all()
    registered_ids = [a["agent_id"] for a in all_agents]
    for aid in ids:
        assert aid in registered_ids


async def test_discovery_event_emitted(registry):
    """Discovery must emit an event dict when flagging unknown agent."""
    unknown_id = f"shadow-{uuid.uuid4()}"
    event = await registry.flag_unknown(unknown_id, return_event=True)
    assert event is not None
    assert event["agent_id"] == unknown_id
    assert event["flagged"] is True
    assert "timestamp" in event


async def test_scanner_finds_new_agents(registry):
    from watchtower.discovery.scanner import AgentScanner
    # Pre-register known agents
    await registry.register("known-agent-1", {})
    # Scanner should detect unknown agents in test namespace
    scanner = AgentScanner(registry=registry, namespaces=["test"])
    # Inject a new agent into the test namespace
    scanner._inject_test_agent("new-unregistered-agent")
    discovered = await scanner.scan()
    assert "new-unregistered-agent" in discovered
