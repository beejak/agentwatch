"""Signal Receiver — consume signals from Redis queue, verify HMAC, forward to Chronicle."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional

from watchtower.core.signal import Signal
from watchtower.receiver.verification import SignalVerifier

logger = logging.getLogger(__name__)


class SignalReceiver:
    """
    Consumes signals from the Redis stream 'wt:signals'.
    Verifies HMAC on every signal. Unverified signals are dropped.
    Verified signals are forwarded to Chronicle (via callback).
    """

    STREAM_KEY = "wt:signals"

    def __init__(
        self,
        redis_client=None,
        verifier: Optional[SignalVerifier] = None,
        secret: str = "watchtower-hmac-secret-change-in-prod",
        on_verified: Optional[Callable[[Signal], None]] = None,
        on_rejected: Optional[Callable[[dict, str], None]] = None,
    ) -> None:
        self._redis = redis_client
        self._verifier = verifier or SignalVerifier()
        self._secret = secret
        self._on_verified = on_verified
        self._on_rejected = on_rejected
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # In-memory queues for testing without Redis
        self._verified_signals: list[Signal] = []
        self._rejected_entries: list[dict] = []

    async def process_entry(self, entry: dict) -> bool:
        """
        Process a single signal entry (dict with 'signal' JSON and 'hmac' field).
        Returns True if verified and forwarded.
        """
        try:
            signal_json = entry.get("signal", "")
            hmac_value = entry.get("hmac", "")

            signal_data = json.loads(signal_json)
            signal = Signal(**signal_data)

            if await self._verifier.verify(signal, hmac_value, self._secret):
                self._verified_signals.append(signal)
                if self._on_verified:
                    self._on_verified(signal)
                return True
            else:
                reason = "HMAC verification failed"
                self._rejected_entries.append({"entry": entry, "reason": reason})
                if self._on_rejected:
                    self._on_rejected(entry, reason)
                logger.warning("Signal rejected: %s — %s", entry.get("signal", "")[:50], reason)
                return False
        except Exception as exc:
            reason = f"Processing error: {exc}"
            self._rejected_entries.append({"entry": entry, "reason": reason})
            if self._on_rejected:
                self._on_rejected(entry, reason)
            logger.error("Signal processing error: %s", exc)
            return False

    async def start(self) -> None:
        """Start consuming from Redis stream."""
        self._running = True
        if self._redis:
            self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Stop the receiver."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self) -> None:
        """Main loop consuming from Redis stream."""
        last_id = "$"
        while self._running:
            try:
                entries = await self._redis.xread(
                    {self.STREAM_KEY: last_id}, count=100, block=100
                )
                for stream, messages in (entries or []):
                    for msg_id, data in messages:
                        last_id = msg_id
                        await self.process_entry(data)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Stream read error: %s", exc)
                await asyncio.sleep(0.1)
