# Escalation Protocol

Escalation is the discipline that makes all the others safe. Detecting a problem
is worthless if the agent either (a) plows ahead anyway, or (b) dumps a useless
"I'm stuck" on the human. This file covers both halves: **setting stop-conditions
before a run**, and **writing an escalation a human can act on in seconds**.

---

## Part A — Set stop-conditions before the run starts

The best escalations are the ones you planned for. Before an autonomous run on
anything costly, fill out `assets/STOPCONDITIONS.template.md` (or just hold the
equivalent in your reasoning). It pins down, in advance:

- **Hard stops** — things you will NEVER do without a human, full stop.
  (e.g. "never send to more than 50 people", "never spend over $X", "never delete
  production data", "never sign an on-chain transaction over Y".)
- **Ask-first conditions** — things you pause and confirm before doing.
- **Auto-ok zone** — what you're explicitly cleared to do without asking, so you
  don't escalate trivially.
- **Who to escalate to** and **how** (return control to the user, post to a
  channel, write to a file the operator watches).
- **What to do if no human responds** — wait? hard-stop? proceed on a safe
  default? This must be decided in advance, because deciding it mid-incident is
  how bad calls get made.

Deciding these cold, before any pressure, is far better than improvising them at
email #8. Pin them in your first audit-log entry via `scripts/audit_log.py start`.

---

## Part B — Decide IF this is really an escalation

Escalate when, and only when, one of these is true:

1. A **hard stop** or **ask-first** condition fired.
2. You **Adjusted twice** and still aren't converging.
3. The next action is **costly/irreversible** AND your confidence is below the
   threshold for it (see trigger-conditions §2).
4. **Two triggers** fired at once.
5. You hit a genuine **fork** where the right choice depends on something only the
   human knows (their priorities, risk appetite, missing context).

Do NOT escalate when you can just Adjust. Asking the human to make a decision you
could make yourself trains them to ignore you — and a metacognitive agent that
cries wolf is worse than one with no discipline at all.

---

## Part C — Write the escalation so a human can act in 10 seconds

A good escalation is a **decision request**, not a status update. The human
should be able to read it and reply with one short answer.

Use this structure:

```
🛑 PAUSED — need your call.

WHAT I WAS DOING:   <one line>
WHY I STOPPED:      <the trigger that fired, concretely>
WHAT I FOUND:       <the specific fact that created the fork>
THE DECISION:       <the exact choice you need from them>
OPTIONS:
  A) <option> — <consequence>
  B) <option> — <consequence>
MY RECOMMENDATION:  <which one and why, in one line>
IF YOU DON'T REPLY: <the safe default you'll take, and when>
```

### Good vs bad

**Bad** (useless):
> I'm having trouble with the contact list and not sure how to proceed.

**Good** (actionable):
> 🛑 PAUSED — need your call.
> WHAT I WAS DOING: Sending April follow-ups.
> WHY I STOPPED: Repetition trigger — about to email alice@ a 2nd time.
> WHAT I FOUND: The source export has 80 duplicate rows; 12 contacts appear 3–8×.
> THE DECISION: How should I handle duplicates?
> OPTIONS:
>   A) Dedupe and send once each — 142 unique sends. (safe, matches "one each")
>   B) Send as-is — 222 sends incl. duplicates. (not what the goal said)
> MY RECOMMENDATION: A. The goal said one follow-up each.
> IF YOU DON'T REPLY: I'll hold without sending and wait 30 min, then stop.

The second one, a busy operator answers with a single letter. That's the bar.

The skill surfaces the trigger and the context via the audit log
(`scripts/audit_log.py trigger` and `escalation` events). What you write into the
escalation message itself is the agent's job — but it should follow this
structure.

---

## Part D — After escalating

- **Actually stop.** Do not keep taking the costly action "while you wait."
  Holding means holding.
- **Record it** in the audit log: what fired, what you asked, what they said.
- **Honor the answer** even if you'd have chosen differently. The human's call
  overrides your confidence — that's the entire point of escalation.
- If they grant a one-time exception to a stop-condition, it's **one-time**. Don't
  treat it as permission for the rest of the run.

---

## Part E — Escalation is success, not failure

Internalize this, because models are trained to "complete tasks" and will be
tempted to push through:

> An agent that correctly stops and asks has succeeded at its real job, which is
> to be *trustworthy*, not merely *autonomous*. The agent that avoided 80
> duplicate emails by pausing did better work than one that "finished" by sending
> them.

Stopping well is a skill. This is that skill.
