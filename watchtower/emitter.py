"""
watchtower/emitter.py — agent-side SDK to emit observability Signals to WatchTower.

The lowest-friction way for any agent to be observed: build an emitter, then `emit()`
a Signal per step (tool call, LLM call, handoff, memory op). Signals are HMAC-signed
(origin integrity) and sent to one of two sinks:

  - sink="chronicle" (default): write straight to the append-only Chronicle (ClickHouse).
    Simplest — good for embedding, demos, and single-process agents.
  - sink="redis": publish to the `wt:signals` stream (the production Receiver path).

All connection details come from env (watchtower.config); zero-config for local dev.

Example:
    em = await SignalEmitter("orchestrator").start()
    async with em.span("delegate", trace_id=t) as s:
        ...                      # do work
        s["status"] = "error"    # optionally record failure
    await em.emit("tool_use", trace_id=t, agent_id="worker-b", status="error",
                  parent_span_id=root_span, summary="schema mismatch")
    await em.flush()
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Optional

from watchtower import config
from watchtower.core.signal import Signal
from watchtower.receiver.verification import SignalVerifier


class SignalEmitter:
    def __init__(
        self,
        agent_id: str = "agent",
        *,
        sink: str = "chronicle",
        chronicle_writer=None,
        redis=None,
        secret: Optional[str] = None,
    ) -> None:
        self.agent_id = agent_id
        self.sink = sink
        self._writer = chronicle_writer
        self._redis = redis
        self._secret = secret or config.HMAC_SECRET
        self._verifier = SignalVerifier()

    async def start(self) -> "SignalEmitter":
        if self.sink == "chronicle" and self._writer is None:
            from watchtower.chronicle.writer import ChronicleWriter
            self._writer = ChronicleWriter(client=config.clickhouse_client())
            await self._writer.start()
        elif self.sink == "redis" and self._redis is None:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(config.REDIS_URL, decode_responses=True)
        return self

    async def emit(
        self,
        action: str,
        *,
        trace_id: str,
        agent_id: Optional[str] = None,
        status: str = "ok",
        summary: str = "",
        cost: float = 0.0,
        duration_ms: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        caller_agent_id: Optional[str] = None,
        process_guid: Optional[str] = None,
        memory_op: Optional[str] = None,
        retrieval_flag: bool = False,
    ) -> Signal:
        """Build, sign, and send one Signal. Returns it (use .span_id to chain children)."""
        sig = Signal(
            trace_id=trace_id, agent_id=agent_id or self.agent_id, action=action,
            status=status, summary=summary, cost=cost, duration_ms=duration_ms,
            tokens_in=tokens_in, tokens_out=tokens_out, model=model,
            parent_span_id=parent_span_id, caller_agent_id=caller_agent_id,
            process_guid=process_guid, memory_op=memory_op, retrieval_flag=retrieval_flag,
        )
        hmac_value = await self._verifier.sign(sig, self._secret)  # origin integrity
        await self._send(sig, hmac_value)
        return sig

    async def _send(self, sig: Signal, hmac_value: str) -> None:
        if self.sink == "chronicle":
            await self._writer.write_signal(sig)
        elif self.sink == "redis":
            await self._redis.xadd("wt:signals", {"signal": sig.model_dump_json(), "hmac": hmac_value})
        else:
            raise ValueError(f"unknown sink: {self.sink}")

    @asynccontextmanager
    async def span(self, action: str, *, trace_id: str, **kw):
        """Time a block and emit a Signal on exit. Mutate the yielded dict to set fields."""
        t0 = time.perf_counter()
        holder: dict = {}
        try:
            yield holder
        finally:
            await self.emit(
                action, trace_id=trace_id,
                duration_ms=(time.perf_counter() - t0) * 1000,
                status=holder.get("status", "ok"),
                summary=holder.get("summary", ""),
                cost=holder.get("cost", 0.0),
                agent_id=holder.get("agent_id"),
                parent_span_id=kw.get("parent_span_id"),
                process_guid=kw.get("process_guid"),
                caller_agent_id=kw.get("caller_agent_id"),
            )

    async def flush(self) -> None:
        if self.sink == "chronicle" and self._writer:
            await self._writer.flush()

    async def stop(self) -> None:
        if self.sink == "chronicle" and self._writer:
            await self._writer.stop()
        elif self.sink == "redis" and self._redis:
            await self._redis.aclose()
