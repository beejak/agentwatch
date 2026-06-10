"""
Minimal OpenAI-compatible LLM client (DeepSeek by default).

Used by (a) the verdict LLM judge (stage-3, sampled, off the hot path) and (b) the
LLM-driven Tier-1 capture agent. Reads config from the environment AT CALL TIME so it
honors runtime configuration, and is a no-op (available()==False) when no key is set —
so the deterministic pipeline and CI run with zero LLM dependency.

Env: LLM_API_KEY (required to enable), LLM_MODEL (default deepseek-chat),
     LLM_BASE_URL (default https://api.deepseek.com), WT_LLM=0 to force-disable.
"""
from __future__ import annotations

import os


def available() -> bool:
    return bool(os.getenv("LLM_API_KEY")) and os.getenv("WT_LLM", "1") != "0"


def model() -> str:
    return os.getenv("LLM_MODEL", "deepseek-chat")


def complete(messages: list[dict], *, temperature: float = 0.0,
             max_tokens: int = 400, timeout: float = 30.0) -> str:
    """One chat completion. Raises if no key / on API error (callers handle fallback)."""
    import openai
    client = openai.OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    )
    resp = client.chat.completions.create(
        model=model(), messages=messages,
        temperature=temperature, max_tokens=max_tokens, timeout=timeout,
    )
    return resp.choices[0].message.content or ""
