# Security policy

## Reporting a vulnerability

If you discover a security issue in this skill — especially anything that
could allow an agent to bypass the gate, tamper with the audit log without
detection, or trick the calibration discipline — please report it privately
rather than opening a public issue.

**Email:** yash.grover@antiersolutions.com

Please include:

- A description of the issue and its impact.
- Steps to reproduce (ideally with one of the included scripts).
- Any known workarounds.

We aim to acknowledge new reports within 48 hours and to ship a fix or a
documented mitigation within 7 days for issues rated High or Critical.

## Scope

In scope:

- Bypasses of `scripts/guard.py` that allow a red-triggered action to execute.
- Hash-chain collisions or weaknesses in `scripts/audit_log.py`.
- Evasion patterns for `scripts/loop_detector.py` that defeat repetition,
  semantic-repetition, or oscillation detection.
- Any way for the agent to alter its own audit log without breaking `verify`.

Out of scope:

- The agent editing its own log by design — this is an *intrinsic* layer.
  Combine with an external runtime watcher (RuntimeAI, ServiceNow, custom)
  for tamper resistance.
- Prompt injection from untrusted input. The skill trusts the operator's
  `--goal`, `--evidence`, and `--stop-conditions`. Sanitize those upstream.

## Threat model

The skill assumes:

- The agent wants to follow the protocol but might be wrong.
- The audit log is readable by humans and external monitoring.
- The runtime can enforce exit codes (this is true for every supported CLI).

The skill does **not** assume:

- The agent is honest. A misaligned agent can edit its own log. (Use external
  runtime enforcement.)
- The agent is well-calibrated. That's exactly what the calibration discipline
  is for.
