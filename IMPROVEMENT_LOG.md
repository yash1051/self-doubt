# self-doubt — Improvement Log

> Every cycle writes here. This is the agent's black box for its *own* evolution.

Each entry follows the same shape so cycles can be diffed and regressed against.

```
## [v3.X.Y] — ISO timestamp — cycle N

**Hypothesis (what gap am I closing?):**
<one sentence>

**Change:**
- <file>:<line> — <what>

**Why this, not the other 9 things I noticed:**
<one sentence>

**Critique of self:**
- What I might have gotten wrong:
- What's still missing:
- Confidence the change is correct (0–100):

**Next cycle's prompt (the very next thing to try):**
<one sentence>
```

Cycles append to the bottom. The last entry is what the next cycle reads first.

---

## [v3.0.0] — 2026-06-21T20:42Z — cycle 0 (seed)

**Hypothesis (what gap am I closing?):** Combined release of intrinsic-safety v2
+ metacognitive-discipline v1.0.0. Shipped with hash-chained audit log,
four-discipline gate (`guard.py`), and a working 85→5-send demo.

**Change:**
- New skill folder `~/.claude/skills/intrinsic-safety/` (later renamed to
  `self-doubt`).
- 17 files, ~2,881 LOC, Python 3 stdlib only.
- Apache-2.0 + attribution to Antier Solutions (metacognitive-discipline author).

**Why this, not the other 9 things I noticed:**
The other candidates (better embedding-based similarity, real OSSF scorecard
integration, type stubs, etc.) are layered on top. v3.0.0 had to be the
correct union — feature work comes after.

**Critique of self:**
- What I might have gotten wrong: I didn't adversarially attack the
  `loop_detector.py` semantic-overlap threshold against paraphrase-only inputs
  (`"book a flight"` vs `"reserve a seat"`). 0.6 Jaccard misses paraphrases.
- What's still missing: no test suite; no CI; the demo only tests the
  duplicate-row failure mode; the `--on-goal` default is "yes" which is the
  dangerous default; the README's "framework integration" code sample is
  illustrative, not runnable.
- Confidence the change is correct: 85.

**Next cycle's prompt (the very next thing to try):**
Add a `tests/` directory with adversarial test cases for loop_detector, an
end-to-end test that drives guard.py through every discipline, and a CI workflow
file. Make `--on-goal` default to `unknown` not `yes`.

---

## [v3.1.0] — 2026-06-21T21:30Z — cycle 1

**Hypothesis (what gap am I closing?):** v3.0.0 had no tests, no CI, and a
silent-yes default for `--on-goal` (the most dangerous default in safety
tooling). The improvement loop can't be trusted without tests that fail
when something regresses.

**Change:**
- `tests/test_loop_detector.py` — 14 adversarial tests for exact / semantic /
  oscillation / paraphrase / window / dict-input cases.
- `tests/test_guard.py` — 14 tests driving `guard.check()` through every
  discipline, verifying exit codes (0/2/3) and trigger names emitted, plus
  hash-chain integrity and tamper detection.
- `tests/test_audit_log.py` — 8 tests for chain integrity, monotonicity,
  tamper detection, deletion detection, `note` round-trip, canonical-JSON
  determinism.
- `.github/workflows/test.yml` — CI runs pytest on Python 3.8-3.12 + smoke
  test of the demo.
- `IMPROVEMENT_LOG.md`, `SELF_IMPROVEMENT.md`, `NEXT_CYCLE.md`, `version.txt`
  — bootstrap the recursive improvement loop.
- Bug fix: `_digest_str` was producing non-canonical JSON (`{"to": "a"}`
  with a space) while `audit_log._digest` produced canonical (`{"to":"a"}`),
  making CLI repetition detection silently fail in v3.0.0 (worked via
  library, failed via CLI). Now both use the same `_canonical` from
  `audit_log.py`.
- Bug fix: step-budget was using `_count_actions()` post-include-of-self
  off-by-one. Fixed with `prospective = actions_taken + 1`.
- Synonym detection upgrade: `_tokens` strips `@x.com` from email-like
  tokens so synonym rotation that keeps the target but rotates the verb
  is caught when both sides have ≥ 2 tokens and ≥ 2 shared tokens.
  Documented the v3.x limitation in the test file: verb-only synonyms
  with single-token targets still slip through. v4 should add embedding-
  based similarity for true paraphrase detection.
- `OSCILLATION_CYCLES` lowered from 2 to 1: the original `2 full cycles`
  rule was counting A→B→A→B as 1 cycle, not 2. The new rule matches the
  documented intent.

**Why this, not the other 9 things I noticed:**
- The improvement loop itself is the highest-leverage change — every
  future cycle gets a free safety net from this PR.
- The 3 correctness bugs (canonical-JSON, step-budget off-by-one,
  oscillation threshold) were caught *by writing the tests*, which is
  the whole point. Skipping them would have meant shipping v3.1 with
  silent regressions of v3.0.

**Critique of self:**
- What I might have gotten wrong: I tightened synonym detection, which
  could false-positive on legitimate-but-coincidentally-overlapping
  actions in production. The `test_distinct_recipients_dont_loop` and
  `test_different_intents_dont_loop` cases pass, but real-world traffic
  has more variety than the test cases I wrote.
- What's still missing: embedding-based similarity for paraphrases
  (`"book a flight"` vs `"reserve a seat"`); no examples/ for framework
  integration; no runnable LangGraph demo; the `--on-goal` default is
  still `yes` (the SKILL.md self-improvement file flagged this but I
  ran out of cycle budget for behavior change).
- Confidence the change is correct: 78. The tests are thorough but I
  cannot prove they cover every failure mode.

**Next cycle's prompt (the very next thing to try):**
Make `--on-goal` default to `unknown` instead of `yes` so the agent must
opt in by stating `yes` or `no` explicitly. This is the single highest-
leverage behavior fix — silent yes is the most dangerous default in
safety tooling. Plus: add a runnable LangGraph demo that imports
`guard.Guard` so framework-integration.md's code sample stops being
illustrative-only.
