# Changelog

All notable changes to this skill are documented here.

## [3.0.0] — 2026-06-22

**Combined release.** v3 merges the two pre-existing intrinsic-safety skills
into a single package:

- `intrinsic-safety` v2 (loop detection, calibration, three-discipline subset)
- `metacognitive-discipline` v1.0.0 (four-discipline protocol, hash-chained
  audit log, escalation ladder, scorecard, framework integration recipes)

### Added
- **`scripts/guard.py`** — unified pre-action gate. Bundles all four disciplines
  into a single call; returns a JSON verdict + exit code the agent loop branches on.
- **Multi-trigger stacking** — two yellows make a red; a trigger fired right
  after a missed prediction is treated as red.
- **Per-reversibility confidence floors** — trivial / reversible / costly /
  irreversible each have their own floor (0 / 50 / 70 / 85).
- **`confidence_no_evidence` trigger** — enforced mechanically when confidence
  ≥70 is stated without an evidence clause.
- **`confidence_rose_after_failure` trigger** — catches rationalization
  (confidence rose by ≥10 points after a missed prediction).
- **`dangerous_tool` whitelist** — `rm`, `drop`, `force_push`,
  `sign_transaction`, etc. always require pause & verify, even at confidence 99.
- **Recipient cap** — fires before a run exceeds the configured N.
- **Step budget** — yellow at 2× expected, red at 4× or hard cap.
- **`note` event type** — free-form context the agent wants preserved.
- **`scripts/check_run.py`** — scorecard with integrity, loops, calibration,
  drift, discipline. Surfaces worst overconfident moments.
- **Hash chain `verify`** — `audit_log.py verify` proves the log wasn't edited.

### Changed
- **Language: Python 3 stdlib** (was POSIX bash + JSONL in v2). Single import
  surface, typed events, library + CLI for every script.
- **Audit log is now hash-chained** (was append-only JSONL in v2). Same file
  format but each event carries `seq` / `prev_hash` / `hash`. The verifier
  detects edits and deletions.
- **Threshold defaults** taken from `metacognitive-discipline`'s
  `trigger-conditions.md`: exact-repetition fires on 3rd identical attempt
  (was 4th in v2); semantic-repetition on 3rd within window (was 3rd in v2 but
  with weaker token-overlap floor); oscillation on 2 full A-B-A-B cycles
  (new in v3).
- **Confidence discipline is enforced by the gate, not by the agent's
  self-report.** A confidence ≥70 without an `--evidence` clause now triggers
  `confidence_no_evidence` (was a documented guideline in v2).

### Preserved from v2
- Token-set Jaccard with 2-token floor for synonym-resistance
  (`"email alice"` / `"message alice"` collide with `"send email to alice"`
  while `"alice"` / `"bob"` / `"carol"` don't false-positive).
- POSIX-portability-conscious file layout (still works on any POSIX shell that
  can call Python 3).
- Honest failure-mode documentation in the README — what this skill *can't*
  do is still called out.

### Fixed
- **`_digest_str` JSON canonicalization mismatch** between `audit_log.py` and
  `guard.py`. Was producing whitespace-sensitive fingerprints that prevented
  repetition detection from firing in CLI mode (only library mode worked). v3
  routes both through the same `_canonical` from `audit_log.py`.
- **`log.sh` broken two-pass string build** in v2 — gone, replaced by Python.

### Removed
- All v2 bash scripts (`log.sh`, `check.sh`, `confidence.sh`, `audit.sh`).
  Replaced by Python equivalents.

### Migration from v2
- Replace `bash log.sh` calls with `python audit_log.py event --type …`.
- Replace `bash check.sh` with `python guard.py` (same exit-code contract).
- Replace `bash confidence.sh` with `python guard.py --confidence … --evidence …`
  (the gate enforces evidence clauses).
- Replace `bash audit.sh` with `python check_run.py`.
- Existing JSONL logs from v2 will **not verify** under v3 (different schema
  and no hash chain). Keep them as historical records; start fresh logs.

## [2.0.0] — 2026-06-22 (intrinsic-safety)

### Added
- Two-tier repetition detection: exact fingerprint + token-set Jaccard with
  2-token floor (catches synonym rotation without false positives).
- Confidence calibration with `evidence_score` heuristic.
- Audit summary (`audit.sh`).
- Regression tests for whitespace/punctuation/synonym evasion.

### Fixed
- `log.sh action` had a broken two-pass string build; collapsed.
- `_similar_count` awk was splitting JSON on whitespace, producing wrong
  fingerprints. Switched to comma-split.

## [1.0.0] — 2026-06-22 (metacognitive-discipline)

Initial release by Antier Solutions. See the upstream README for full details.

### Added
- Four core disciplines: repetition awareness, confidence calibration,
  goal-drift detection, escalation discipline.
- `references/trigger-conditions.md` — concrete intervention thresholds.
- `references/escalation-protocol.md` — how to set stop-conditions and write
  actionable escalations.
- `references/audit-log-format.md` — inline + hash-chained file log spec.
- `references/calibration-guide.md` — honest-confidence rubric and overconfidence
  tells.
- `references/framework-integration.md` — LangGraph / CrewAI / OpenAI Agents SDK
  / plain-loop wiring.
- `scripts/audit_log.py` — tamper-evident hash-chained JSONL audit log (CLI +
  library), with `verify`.
- `scripts/loop_detector.py` — exact / semantic / oscillation loop detection,
  zero dependencies.
- `scripts/check_run.py` — post-hoc scorecard: integrity, loops, calibration,
  discipline.
- `assets/STOPCONDITIONS.template.md` — pre-run stop-conditions worksheet.
- `examples/demo_email_loop.py` — the 89-email-loop showcase, with/without.
