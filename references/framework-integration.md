# Framework Integration

The four disciplines are framework-agnostic — they're reasoning habits, not code.
But in production you usually want them enforced *mechanically* too, so a model
having a bad day can't simply skip the check. This file shows how to wire the
disciplines into common agent runtimes as real interceptors, using the bundled
scripts.

The pattern is always the same: **intercept before each tool call, run the
checks, log, and gate.** Below are concrete shapes for the popular frameworks.

---

## Plain tool-call loop (no framework)

The reference implementation. Everything else is a variation on this.

```python
from scripts.guard import Guard
from scripts.audit_log import AuditLog

log = AuditLog.start(goal="Send April follow-ups", expected_steps=150)
guard = Guard(log_path=log.path, goal="Send April follow-ups", expected_steps=150)
recent_actions = []

def guarded_call(action, args, confidence, evidence, on_goal, reversibility="costly"):
    # The Guard does all four disciplines + writes the audit trail.
    verdict = guard.check(
        action=action, args=args,
        confidence=confidence, evidence=evidence,
        on_goal=on_goal, reversibility=reversibility,
        recipients_this_run=...,   # tracked by your caller
    )

    if verdict.verdict == "red":
        guard.escalate(
            asked="...", options=["A", "B"], recommendation="A",
            answer="A", responder="operator",
        )
        # Stop and wait. Holding means holding.
        return escalate_or_adjust(...)

    if verdict.verdict == "yellow":
        # Proceed but record the warning.
        guard.note(f"yellow trigger: {verdict.reasons}")

    # green or yellow: proceed.
    predicted = "..."  # your prediction for the post_action record
    result = do(action, args)
    guard.observed(
        action=action, predicted=predicted, observed=str(result),
        confidence_was=confidence, confidence_should=confidence, note="",
    )
    return result
```

The key property: the gate sits *between* the agent's decision and the side
effect. The agent can want to send email #89; the gate is what stops it.

---

## LangGraph

LangGraph is a state graph, so add the discipline as a node that every
tool-executing edge passes through.

- Add `goal`, `expected_steps`, `recipients_this_run`, and `audit_log_path` to
  your graph **state**.
- Insert a **`metacog_gate` node** before the tool node. It runs the same check
  as above (using `Guard.check`) and routes:
  `green/yellow → tool node`, `red → interrupt`.
- Use LangGraph's built-in `interrupt()` for escalation — it natively supports
  human-in-the-loop pauses, which is exactly the escalation primitive you want.
- Persist the audit log alongside the graph checkpoint so a resumed run keeps its
  history (and its loop awareness).

---

## CrewAI

CrewAI is role/task based, so attach discipline at the tool and task level.

- Wrap each tool in a thin decorator that calls `guarded_call`. CrewAI tools are
  just callables; the wrapper is transparent to the crew.
- Put the **goal** and **stop-conditions** into the task description so every
  agent in the crew shares them — drift is worse in multi-agent setups because
  each agent can wander independently.
- Use a shared audit log file across the crew so repetition is detected *across*
  agents, not just within one. Two agents redundantly doing the same thing is a
  common crew failure the per-agent view misses.

---

## OpenAI Agents SDK

- Use **guardrails / tool-call hooks** to run the pre-action check before each
  function call; the SDK exposes hooks around tool execution.
- Enforce the confidence gate by having the model emit a structured
  `{action, confidence, evidence}` object (function-calling schema), then gating
  in your hook — don't trust prose confidence; require the structured field.
- Route escalations back through the SDK's handoff mechanism to a human or a
  supervisor agent.

---

## Model-internal only (no code path)

Sometimes you can't add interceptors (you're inside a hosted assistant, a chat
UI, or a no-code builder). Then the disciplines run purely in reasoning:

- Keep the inline audit log in your chain of thought (the markers in
  `audit-log-format.md`).
- Do the four-question pre-action check in text before each consequential step.
- Self-enforce the thresholds from `trigger-conditions.md`.

This is weaker than a hard gate — a model *can* skip a habit it can't skip a code
check — but it still catches the large majority of loops and drift, because the
failure was usually "never thought to check," not "checked and overrode."

---

## A note on cost

The disciplines add tokens: a few lines of reasoning per consequential step, plus
optional script calls. In practice this is a rounding error next to the cost of a
runaway loop (89 wasted LLM+email calls, or one bad irreversible action). Scale
the ceremony to the stakes — full discipline on costly autonomous runs, minimal
on cheap reversible ones. See SKILL.md Step 0.
