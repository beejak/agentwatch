# Attribution

This repository was developed with assistance from AI language model tools.

AI assistance was used for:
- Code generation and iteration across the 16-layer detection architecture
- Test case design and adversarial payload generation
- Documentation writing
- Debugging and root cause analysis during development

All code has been reviewed, tested, and validated against the gate suite
before being committed. The detection logic, MAST taxonomy mapping, and
security invariants represent deliberate design decisions, not generated defaults.

## Human Decisions

The following were decided by human judgment, not generated:
- Architecture: which layers to build and how they compose
- Security invariants: Chronicle append-only, default-deny policy, HMAC verification
- Detection thresholds: calibrated against real token pricing and production FP budgets
- Which attacks to prioritize (MINJA, SpAIware, SC1/SC2/SC3)
- Production integration strategy (shadow mode → enforcement mode)

## Testing

The detection system is validated by:
- 207 automated tests (static)
- Agentic tester (`agents/agentic_tester/`) that uses LLMs to generate novel attack payloads
  and probe for gaps that static tests cannot find

See `docs/SUCCESS_CRITERIA.md` for full pass/fail definitions.
