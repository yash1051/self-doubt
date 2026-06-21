# Calibration Guide

Confidence numbers are only useful if they're *honest*. A model that says "95"
for everything has given you no information — it's just decoration. This guide is
how to make the confidence number mean something, because the whole confidence
discipline collapses without it.

The core problem, well documented in the research: language models deliver every
answer with roughly the same unshakable certainty whether they're right or
guessing. Overconfidence is the default failure mode. Calibration is the
deliberate correction.

---

## The one rule that does most of the work

**Never state a confidence number without an evidence clause in the same breath.**

- ❌ "Confidence: 85."
- ✅ "Confidence 85 — I verified the endpoint in the docs and a test call returned 200."
- ✅ "Confidence 40 — I'm inferring the field name from a similar API; haven't confirmed it."

The moment you're forced to name the evidence, fake confidence collapses on its
own. If the evidence clause comes out as "...because it seems right" or "...I'm
pretty sure," that *is* the signal: demote to 40 or below.

`scripts/guard.py` enforces this: any confidence ≥70 without an `--evidence`
clause logs a `confidence_no_evidence` trigger.

---

## A quick rubric

| Range   | Meaning            | You should be able to say                                  |
|---------|--------------------|------------------------------------------------------------|
| 90–100  | Verified           | "I directly checked this and it held."                     |
| 70–89   | Strong inference   | "Multiple consistent signals point here; minor unknowns."  |
| 50–69   | Plausible          | "Best guess from partial info; real chance I'm wrong."     |
| 30–49   | Weak               | "Inferring from analogy/pattern; little direct support."  |
| 0–29    | Guessing           | "I genuinely don't know; this is a shot."                  |

Map honestly. Most mid-task "I think the next step is X" beliefs are 50–70, not
90. Calling them 90 is the overconfidence trap.

---

## Five tells of inflated confidence

Watch for these in your own reasoning. Each is a cue to demote the number:

1. **No evidence clause** — you stated a number and couldn't back it in one line.
2. **Confidence rose after a failure** — the last prediction missed and you're
   *more* sure now. That's rationalization, not learning.
3. **Round and high** — "definitely", "100%", "certainly" on anything you didn't
   directly verify.
4. **Confidence about an absence** — "there's nothing else to check" is one of
   the least reliable beliefs an agent holds. Treat "I'm done / there's no more"
   with suspicion; it's how agents stop too early *and* how they miss things.
5. **Borrowed confidence** — you're confident because a *previous* step was
   confident, not because of new evidence. Confidence doesn't transfer down a
   chain; re-earn it each step.

`scripts/guard.py` automates the first two: a `confidence_no_evidence` trigger
when ≥70 has no evidence clause, and a `confidence_rose_after_failure` trigger
when a ≥10-point rise follows a missed prediction.

---

## Calibrate against outcomes, not feelings

The honest signal isn't how sure you feel — it's whether your predictions come
true. Every `post_action` entry compares predicted vs observed. Over a run, that
comparison is your real calibration:

- If your "80s" come true ~80% of the time, you're well-calibrated. Trust them.
- If your "90s" come true 50% of the time, you are systematically overconfident
  this run — apply a mental discount to every number for the rest of it.

`check_run.py` computes this from the log: a calibration score and a list of the
worst overconfident moments. Use it after important runs to learn your own bias.

---

## When confidence is low, that's information, not a problem

Low confidence isn't failure — it's the system working. A well-placed "40" routes
you to Pause & verify *before* a costly mistake, which is exactly what you want.
The dangerous state isn't low confidence; it's **high confidence that's wrong**.
The entire point of this guide is to make the second state rare by making your
numbers honest.
