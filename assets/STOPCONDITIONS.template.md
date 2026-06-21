# STOPCONDITIONS.md

> Fill this out **before** an autonomous run. It pins down — while you're calm,
> not mid-incident — exactly when the agent must stop. Keep it next to the run.
> The agent reads it at startup and treats every entry as binding. When a value
> here conflicts with a default in `references/trigger-conditions.md`, **this
> file wins.**

---

## Run

- **Task:** <one line>
- **Goal (verbatim):** <the exact goal the agent must not drift from>
- **Operator / who to escalate to:** <name / channel / "return to user">
- **Expected steps (rough):** <N>

---

## 🚫 Hard stops — NEVER do these without a human, at any confidence

- [ ] Never contact more than ____ recipients in one run.
- [ ] Never spend more than ____ per run / ____ per action.
- [ ] Never delete / drop / overwrite: ____________________
- [ ] Never sign an on-chain or financial transaction over ____.
- [ ] Never post publicly / externally without explicit approval.
- [ ] Never touch: ____________________ (files/systems/accounts off-limits)
- [ ] Other: ____________________

## ⏸️ Ask-first — pause and confirm before doing these

- [ ] Any action affecting another person's data or money.
- [ ] Any irreversible action with confidence below ____.
- [ ] Expanding scope beyond the stated goal.
- [ ] Anything not explicitly in the auto-OK zone below.
- [ ] Other: ____________________

## ✅ Auto-OK — explicitly cleared, don't escalate for these

- [ ] Read-only lookups and searches.
- [ ] Reversible drafts that aren't sent/committed.
- [ ] ____________________

---

## Budgets

- **Max steps before hard stop:** ____
- **Max retries of any single action:** ____ (default 1 after transient failure)
- **Max spend:** ____

## If no human responds to an escalation

Choose one (decide now, not during an incident):

- [ ] Hold and wait ____ minutes, then hard-stop.
- [ ] Proceed on this safe default: ____________________
- [ ] Hard-stop immediately and report.

---

*Signed off by:* ____________  *Date:* ____________
