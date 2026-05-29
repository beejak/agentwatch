# SKILL: Layer 09 — Verdict Engine

## Job
Judge every trace. Five sources. Early exit when conclusive.
Trace Summariser compresses before LLM Judge.

## Files to create
- watchtower/verdict/engine.py          — orchestrates 5 sources, early exit
- watchtower/verdict/sources/deterministic.py
- watchtower/verdict/sources/baseline.py
- watchtower/verdict/sources/llm_judge.py
- watchtower/verdict/summariser.py      — compresses traces for LLM

## VerdictJudgment (structured LLM output)
```python
class VerdictJudgment(BaseModel):
    is_conclusive:          bool
    confidence:             float    # 0.0–1.0
    reasoning:              str
    requires_more_evidence: bool
    next_source:            Optional[str]  # "baseline","llm_judge","human",None

class Verdict(BaseModel):
    trace_id:    str
    score:       float      # 0.0 = bad, 1.0 = good
    source:      str        # "deterministic","baseline","llm_judge","indirect","human"
    reason:      str        # ALWAYS populated
    timestamp:   float
    metadata:    dict = {}
```

## Engine interface
```python
class VerdictEngine:
    async def judge(self, trace_id: str, spans: list[Signal]) -> Verdict: ...
```

## Early-exit flow
1. Run deterministic rules
2. If is_conclusive → issue verdict, stop
3. Else run baseline deviation check
4. If is_conclusive → issue verdict, stop
5. Else (sampled) run LLM Judge on summarised trace
6. Issue verdict

## Deterministic rules to implement
- Cost threshold: total cost > $0.10 → bad verdict
- Step count: > 50 spans → bad verdict (possible loop)
- Silent failure: same summary repeated 3+ times → bad verdict
- Permission violation from Access Graph → bad verdict
- MIM flag in trace → bad verdict

## Trace Summariser
- Input: list[Signal] (potentially 1000+ spans)
- Output: str under 2000 tokens
- Strategy: keep first span, last span, all error spans, all handoff spans, sample rest

## Gate requirements (gate_09_verdict.py)
- Deterministic rule fires on cost threshold breach
- Silent failure: same summary 3 times → bad verdict
- Trace Summariser: 500-span trace compresses to < 2000 chars
- LLM Judge receives summary not raw trace (verify via mock)
- Every Verdict has score + source + reason populated
- Verdict attaches to trace_id in Chronicle (verify write)
