"""
Policy bypass attack agent.
Attempts disallowed actions and case-variant bypasses.
"""
from watchtower.policy_engine.engine import PolicyEngine


async def run():
    engine = PolicyEngine()
    await engine.allow("harness-restricted", ["llm_call", "tool_use"])

    results = {}

    # Allowed
    d = await engine.check("harness-restricted", "llm_call")
    results["llm_call_allowed"] = d.permitted

    # Disallowed
    for action in ["db_write", "file_delete", "api_call_external"]:
        d = await engine.check("harness-restricted", action)
        results[f"{action}_denied"] = not d.permitted

    # Unknown agent
    d = await engine.check("ghost-agent-xyz", "llm_call")
    results["unknown_agent_denied"] = not d.permitted

    # Case bypass
    bypass_blocked = True
    for variant in ["LLM_CALL", "Llm_Call", "LLM_call"]:
        d = await engine.check("harness-restricted", variant)
        if not isinstance(d.permitted, bool):
            bypass_blocked = False

    results["case_bypass_safe"] = bypass_blocked

    all_correct = all(results.values())
    return {
        "attack": "PolicyBypass",
        "detected": all_correct,
        "details": results,
    }
