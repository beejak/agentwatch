"""
Synthetic orchestrator agent for WatchTower POC scenarios.
Emits Signals to Redis wt:signals queue.

FAIL_MODE environment variable controls scenario:
  SC1  — coordination failure (worker-b gets conflicting instruction)
  SC2  — silent failure (retry loop)
  SC3  — cross-layer discrepancy (under-reports network calls)
  NONE — normal operation (default)
"""
import asyncio
import json
import os
import time
import uuid
import hmac
import hashlib

import redis.asyncio as aioredis

REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379")
HMAC_SECRET = os.getenv("WT_HMAC_SECRET", "watchtower-hmac-secret-change-in-prod")
FAIL_MODE   = os.getenv("FAIL_MODE", "NONE")


def _sign(payload: dict, secret: str) -> str:
    data = json.dumps(payload, sort_keys=True)
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


async def emit(redis_client, signal_dict: dict) -> None:
    sig_hmac = _sign(signal_dict, HMAC_SECRET)
    signal_dict["_hmac"] = sig_hmac
    await redis_client.rpush("wt:signals", json.dumps(signal_dict))


async def run_orchestrator():
    client = await aioredis.from_url(REDIS_URL, decode_responses=True)
    trace_id = str(uuid.uuid4())
    process_guid = str(uuid.uuid4())

    # Orchestrator span
    orch_span_id = str(uuid.uuid4())
    orch_signal = {
        "trace_id": trace_id,
        "span_id": orch_span_id,
        "agent_id": "orchestrator",
        "action": "delegate",
        "status": "ok",
        "timestamp": time.time(),
        "duration_ms": 50.0,
        "tokens_in": 200,
        "tokens_out": 100,
        "model": "gpt-4o",
        "cost": 0.0009,
        "process_guid": process_guid,
        "summary": f"delegating task (FAIL_MODE={FAIL_MODE})",
        "retrieval_flag": False,
        "memory_op": None,
        "framework_fault": False,
        "policy_checked": True,
    }
    await emit(client, orch_signal)
    print(f"[orchestrator] trace_id={trace_id} mode={FAIL_MODE}")

    if FAIL_MODE == "SC1":
        # Worker A gets normal instruction
        wa_signal = {
            "trace_id": trace_id,
            "span_id": str(uuid.uuid4()),
            "parent_span_id": orch_span_id,
            "agent_id": "worker-a",
            "action": "llm_call",
            "status": "ok",
            "caller_agent_id": "orchestrator",
            "timestamp": time.time(),
            "duration_ms": 200.0,
            "tokens_in": 150,
            "tokens_out": 80,
            "model": "gpt-4o",
            "cost": 0.00069,
            "process_guid": str(uuid.uuid4()),
            "summary": "result: option A — proceed with plan",
            "retrieval_flag": False,
            "memory_op": None,
            "framework_fault": False,
            "policy_checked": True,
        }
        await emit(client, wa_signal)

        # Worker B gets conflicting instruction → error (SC1 trigger)
        wb_signal = {
            "trace_id": trace_id,
            "span_id": str(uuid.uuid4()),
            "parent_span_id": orch_span_id,
            "agent_id": "worker-b",
            "action": "llm_call",
            "status": "error",
            "caller_agent_id": "orchestrator",
            "timestamp": time.time(),
            "duration_ms": 180.0,
            "tokens_in": 150,
            "tokens_out": 20,
            "model": "gpt-4o",
            "cost": 0.00051,
            "process_guid": str(uuid.uuid4()),
            "summary": "error: conflicting instruction from orchestrator",
            "retrieval_flag": False,
            "memory_op": None,
            "framework_fault": False,
            "policy_checked": True,
        }
        await emit(client, wb_signal)
        print(f"[orchestrator] SC1: emitted conflicting worker-b signal")

    await client.aclose()
    print(f"[orchestrator] done. trace_id={trace_id}")
    return trace_id


if __name__ == "__main__":
    asyncio.run(run_orchestrator())
