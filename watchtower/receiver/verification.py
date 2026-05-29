"""HMAC origin verification for signals."""
from __future__ import annotations

import hashlib
import hmac
import json

from watchtower.core.signal import Signal


class SignalVerifier:
    """Sign and verify signals using HMAC-SHA256."""

    async def sign(self, signal: Signal, secret: str) -> str:
        """Return HMAC-SHA256 hex digest of the signal JSON."""
        payload = json.dumps(signal.model_dump(), sort_keys=True, default=str)
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def verify(self, signal: Signal, hmac_value: str, secret: str) -> bool:
        """Return True if the HMAC matches the signal content."""
        expected = await self.sign(signal, secret)
        return hmac.compare_digest(expected, hmac_value)
