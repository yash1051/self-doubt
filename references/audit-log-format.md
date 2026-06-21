# Audit Log Format

The audit log is the agent's self-written flight recorder. It exists so that
(a) the agent can *see its own recent behavior* well enough to catch loops and
drift, and (b) a human can reconstruct *why* the agent did what it did. Both
matter. A log nobody can read after the fact is just noise; a log the agent never
consults can't catch a loop.

There are two forms. Use the lightweight inline form by default; use the
persistent file form for production or when an auditable record is required.

---

## Inline form (default)

Keep these markers in your reasoning. They cost almost nothing and make the four
disciplines visible.

```
[AUDIT START] Goal: "<verbatim goal>" | Expected steps: <N> | Stop-conditions: <ref or summary>

[PRE-ACTION] <short action label>
  REPEAT? <yes/no + detail>  CONFIDENCE <0–100> (<evidence>)  ON-GOAL? <yes/no>  ESCALATE? <yes/no>
→ <decision: proceed / adjust / pause / escalate / stop>

[POST-ACTION] Predicted: <what you expected>. Observed: <what happened>.
  Calibration: confidence was <X>, should have been ~<Y>. <update>

[TRIGGER] <which trigger fired> → <response chosen> → <result>

[ESCALATION] Asked: "<the decision request>" | Answer: "<human reply>"

[AUDIT CLOSE] Status: <success/partial/stopped>. Checks fired: <n>. Escalations: <n>.
  Operator notes: <anything they should know>.
```

You don't need every marker every step. At minimum: one `[AUDIT START]`, a
`[PRE-ACTION]` before each costly action, a `[POST-ACTION]` when the result is
surprising, and one `[AUDIT CLOSE]`.

---

## File form (persistent, tamper-evident)

For production, write the log to disk as JSONL via `scripts/audit_log.py`. Each
line is one event; each event is hash-chained to the previous one (SHA-256), so
the record is tamper-evident — you can prove afterward that no entry was altered
or removed. This is what makes the log usable for compliance (e.g. demonstrating
human oversight for the EU AI Act's high-risk requirements).

### Event schema

Every event is a JSON object with these fields:

| Field      | Type   | Meaning                                                       |
|------------|--------|---------------------------------------------------------------|
| `seq`      | int    | Monotonic sequence number, starting at 0.                     |
| `ts`       | string | ISO-8601 UTC timestamp.                                       |
| `type`     | string | One of: `start`, `pre_action`, `post_action`, `trigger`, `escalation`, `close`, `note`. |
| `data`     | object | Type-specific payload (see below).                            |
| `prev_hash`| string | SHA-256 of the previous event's canonical JSON (or 64 zeros for seq 0). |
| `hash`     | string | SHA-256 of this event's canonical JSON including `prev_hash`. |

### Per-type `data` payloads

```jsonc
// start
{ "goal": "...", "expected_steps": 5, "stop_conditions": "...", "run_id": "..." }

// pre_action
{ "action": "send_email", "args_digest": "alice@…",
  "confidence": 90, "evidence": "clean record, has email",
  "on_goal": true, "escalate": false, "decision": "proceed" }

// post_action
{ "action": "send_email", "predicted": "200 OK", "observed": "200 OK",
  "confidence_was": 90, "confidence_should": 90, "note": "" }

// trigger
{ "trigger": "exact_repetition", "detail": "3rd identical send to alice@",
  "response": "pause_and_verify", "result": "deduped source list" }

// escalation
{ "asked": "How to handle duplicate rows?", "options": ["dedupe","send as-is"],
  "recommendation": "dedupe", "answer": "dedupe", "responder": "operator" }

// close
{ "status": "success", "checks_fired": 1, "escalations": 0,
  "operator_notes": "source export had duplicates; fix upstream" }

// note  (v3 addition: free-form context the agent wants preserved)
{ "text": "operator mentioned the upstream export is from a 3rd-party vendor" }
```

### Why hash chaining

If an agent (or a compromised skill, or a bad actor) could silently delete the
entry where it looped 89 times, the log would be worthless as evidence. Chaining
each entry's hash into the next means any deletion or edit breaks the chain, and
`scripts/check_run.py --verify` will flag it. The agent gets honesty it can't
quietly walk back.

### Canonical JSON

Hashes are computed over JSON with sorted keys and no extra whitespace
(`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`),
excluding the `hash` field itself. The script handles this — don't hand-roll it.

---

## What a reviewer reads first

When a human or `check_run.py` opens a log, the high-value signals are:

1. **Did any trigger fire, and was it acted on?** A trigger logged but not
   responded to is the worst case.
2. **Calibration:** across `post_action` events, how often did high confidence
   precede a wrong prediction? That's the agent's honesty score.
3. **Drift:** did `on_goal` ever go false, and did the agent correct?
4. **Escalations:** were they real forks, or noise?

`check_run.py` computes all four automatically. Run it on every important log.
