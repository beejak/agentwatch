# Lessons Learned — Cross-Repo Engineering Playbook

**Purpose.** A portable, structured record of mistakes made and the rules to never repeat
them. Written to be **dropped into any repo** and handed to Claude Code (or any engineer):
*"read LESSONS_LEARNED.md before you work, and check your changes against it."*

**How to use.**
- At the **start** of a task: read the Pre-flight checklist + the relevant section.
- Before **commit/push/merge**: re-check the Git/CI sections.
- At the **end** of a session: append new lessons (date them). Keep entries
  *generic rules* with a one-line concrete example — so they transfer across repos.

**Format.** Each lesson = **Rule** (imperative, generic) → *what happened* (the concrete
mistake) → *why*. Keep it terse and actionable.

---

## ✅ Pre-flight checklist (the distilled rules)

- [ ] **Enumerate all top-level dirs and follow test imports before claiming what a repo does or doesn't contain.**
- [ ] **After `git rm` + edits, run `git status` and `git diff --cached --stat`; confirm EVERY intended file is staged before committing.**
- [ ] **Never pass a stale/nonexistent path to `git add`** — a fatal pathspec aborts the whole add → silent partial commit.
- [ ] **Confirm CI runs the FULL test suite, not a subset.**
- [ ] **No YAML anchors in GitHub Actions** — use job-level `env`.
- [ ] **Pin git dependencies to a tag, not a branch.**
- [ ] **Use tolerance for float assertions.**
- [ ] **Held-out split + baselines + confidence intervals before any headline metric.** Never report a % on a small or self-tuned corpus.
- [ ] **One owner of the default branch; short-lived branches; branch → PR → CI → merge → delete.**
- [ ] **Verify before outward/irreversible actions; verify again after.**
- [ ] **State what is real vs. simulated; disclose limitations rather than hide them.**

---

## 1. Git / version control

- **Rule: a bad pathspec aborts the entire `git add`.** → *Happened:* `git add README.md Makefile watchtower/taint_graph …` hit a fatal error on the already-deleted `taint_graph` path; nothing in that command staged, so the README/Makefile edits silently never committed — the PR only carried the earlier `git rm` deletions. *Why:* git aborts the add atomically on a fatal pathspec. **Always diff the staged set before commit.**
- **Rule: rebase-merge rewrites commit SHAs** — local branch SHAs won't match `origin/master` after a squash/rebase merge; always `git fetch` + `--ff-only` to resync, then delete the local branch.
- **Rule: extract subtrees with history** — use `git filter-repo` (not a fresh copy) when splitting a repo, so provenance survives.
- **Rule: untracked changes follow branch checkouts** — uncommitted edits silently ride along across branches; they can hide unfinished work. Keep the tree clean between branches.

## 2. CI / CD

- **Rule: GitHub Actions does NOT support YAML anchors (`&`/`*`).** → *Happened:* hoisted an `env` block with an anchor; would have broken the workflow. **Use job-level `env`** to share across steps.
- **Rule: make CI run the full suite.** → *Happened:* CI ran only `gate-all` + `poc`; integration/eval tests were never gated (passed locally, never in CI). **Check what CI actually executes.**
- **Rule: a PR is the only way to get CI to gate before merge** when branch-pushes don't trigger workflows. Don't "push but never merge" — that gets zero CI.
- **Rule: hatchling needs `[tool.hatch.metadata] allow-direct-references = true`** for `pkg @ git+https://…` dependencies, or `pip install -e .` fails in CI.
- **Rule: pin cross-repo git deps to a tag**, never a moving branch — reproducibility.

## 3. Testing

- **Rule: never assert float equality** (`x == 0.64`); use `abs(x - 0.64) < 1e-9`. → *Happened:* `0.8*0.8 == 0.64` failed (`0.6400000000000001`).
- **Rule: freeze generated artifacts; strip volatile fields** (timestamps) or `.gitignore` them — a `generated_at` field dirties the tree on every run.
- **Rule: measure coverage across ALL packages**, not just the main one — gaps hide in adapters/aux modules.
- **Rule: distinguish tests from eval.** Tests = correctness (green/red). Eval = quality (metrics). Don't conflate; build both.

## 4. Research / evaluation integrity

- **Rule: 100% on a small, hand-curated, self-tuned corpus is the overfitting trap, not a result.** → *Happened:* a prior "100% on 17 cases" claim; our own mock corpus scored 100% while held-out novel inputs scored 82%. The gap *is* the overfit. **Held-out + baselines + CIs, or it doesn't count.**
- **Rule: regex/keyword matching is a tier-0 filter, never the detector of record** — against an adaptive (white-box) adversary it's whack-a-mole; it can't see intent, and FP/FN are structural.
- **Rule: ground truth must be independent of the system under test** — don't let the model that generates attacks also label them; use human/task-derived labels.
- **Rule: comparisons must be apples-to-apples** — don't compare your rule-lookup latency to a competitor's end-to-end semantic latency.
- **Rule: evidence flows repo → paper, never the reverse.** Tune the system to reality; if data contradicts a claim, change the claim. Preserve all data; tag the evidence commit.
- **Rule: be explicit about "real" vs "realistic/simulated."** Capture limitations honestly; a disclosed limitation is credibility, a hidden one is a liability.

## 5. Architecture / repo structure

- **Rule: verify what exists before asserting absence.** → *Happened:* analyzed only one package and wrongly declared "the system isn't implemented"; it was in sibling dirs (`firewall/`, `agents/adapters/`) reached via the test imports. **Open every top-level dir; follow imports.** Retract immediately when wrong.
- **Rule: harden the substrate before building on it.** A dependency (library) should be frozen/stable before you iterate on the thing that pins it.
- **Rule: one-directional dependency + a package boundary before a hard split.** Two systems in one repo cause confusion; split when one is immature and drags the mature one — but split for the *right reason* (drag/immaturity), not mere tidiness.

## 6. Process / collaboration

- **Rule: ask before tough/irreversible decisions that affect repos** (visibility, deleting code, force-push); proceed on the obvious with a note otherwise.
- **Rule: correct the record the moment you find you were wrong** — don't defend a prior analysis.
- **Rule: don't over-claim "done"** — report what passed, what was skipped, with the evidence.

---

## Session log (append per session; newest first)

### 2026-06 — agentwatch / watchtower observability + firewall split
- All of §1–§6 above were learned or reinforced here. Highlights: the `git add` partial-commit
  bug (§1), CI running only a subset (§2), the firewall-vs-watchtower mis-analysis (§5), the
  mock-100%-vs-held-out-82% overfitting demonstration (§4), and the repo-first evidence
  philosophy (§4). Established the branch→PR→CI→merge workflow with one owner of `master`.
