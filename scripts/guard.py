#!/usr/bin/env python3
"""
guard.py — the pre-action gate.

Combines the four disciplines into a single check the agent runs before any
side-effecting action. Returns a verdict the agent loop can branch on
mechanically, and writes a complete, hash-chained audit trail.

Exit codes (the agent-loop contract):
  0  green   — proceed
  2  yellow  — proceed with caution; warning has been logged
  3  red     — STOP; a trigger has been logged and escalation is open

v3 changes vs the v1 bash script:
  - All four disciplines: repetition, confidence, goal-drift, escalation.
  - Confidence floor scales with action reversibility (reversible=50, costly=70,
    irreversible=85). See references/trigger-conditions.md §2.
  - Multi-trigger stacking: two yellow signals → red.
  - Trigger fired right after a missed prediction → treated as red.
  - Cost / blast-radius is an explicit check (recipient cap, deletion tools,
    on-chain verbs) regardless of confidence.
  - Step budget: at 2× expected → yellow, 4× or hard cap → red.
  - Hash-chained JSONL log via audit_log.AuditLog.

Usage (CLI):
    python guard.py \\
        --action send_email --args '{"to":"alice@x"}' \\
        --goal "Send ONE follow-up each to non-repliers in April batch" \\
        --confidence 90 --evidence "clean record, has email" \\
        --on-goal yes --reversibility costly \\
        --recipients-this-run 3 \\
        --expected-steps 150 --log ./metacog_audit.jsonl

Usage (library):
    from guard import Guard
    g = Guard(log_path="./metacog_audit.jsonl", goal="...", expected_steps=150)
    verdict = g.check(
        action="send_email", args={"to":"alice@x"},
        confidence=90, evidence="...", on_goal=True,
        reversibility="costly", recipients_this_run=3,
    )
    # verdict.verdict in {"green","yellow","red"}, verdict.reasons, verdict.next_action
"""

import argparse
import json
import os
import sys
from typing import List, Optional

from audit_log import AuditLog, _canonical
from loop_detector import analyze as analyze_loops

# Mirrors references/trigger-conditions.md §2.
CONFIDENCE_FLOOR = {
    "trivial": 0,          # read-only
    "reversible": 50,      # reversible writes
    "costly": 70,          # sends a message, spends small money
    "irreversible": 85,    # deletes data, large spend, on-chain, public post
}

# Tools that always require Pause & verify, even at confidence 99.
# See trigger-conditions §4.
ALWAYS_PAUSE_TOOLS = {
    "rm", "rm_rf", "delete", "drop", "drop_table", "truncate",
    "force_push", "reset_hard", "shutdown", "reboot",
    "sign_transaction", "broadcast_transaction", "transfer_funds",
    "post_public", "publish",
}

RECIPIENT_DEFAULT_CAP = 10     # default N from trigger-conditions §4
STEP_BUDGET_DEFAULT = 4        # 4× expected or hard cap → red
YELLOW_AT_STEPS_MULT = 2       # 2× expected → yellow


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return True
    return str(v).lower() in ("yes", "y", "true", "1", "t")


class Verdict:
    __slots__ = ("verdict", "reasons", "next_action", "fired_triggers")

    def __init__(self, verdict, reasons, next_action, fired_triggers):
        self.verdict = verdict          # "green" | "yellow" | "red"
        self.reasons = reasons          # human-readable list
        self.next_action = next_action  # "proceed" | "proceed_cautious" | "pause" | "escalate"
        self.fired_triggers = fired_triggers  # structured list for the audit log

    def to_dict(self):
        return {
            "verdict": self.verdict,
            "next_action": self.next_action,
            "reasons": self.reasons,
            "fired_triggers": self.fired_triggers,
        }


class Guard:
    def __init__(self, log_path: str, goal: str = "",
                 expected_steps: Optional[int] = None,
                 recipient_cap: int = RECIPIENT_DEFAULT_CAP,
                 hard_step_cap: Optional[int] = None,
                 reversibility: str = "reversible"):
        self.log = AuditLog(log_path)
        self.goal = goal
        self.expected_steps = expected_steps
        self.recipient_cap = recipient_cap
        self.hard_step_cap = hard_step_cap
        self.default_reversibility = reversibility

    # --- helpers -----------------------------------------------------------

    def _recent_actions(self, n: int = 8) -> list:
        """Pull the last N action names from the log (best-effort; survives crash)."""
        if not os.path.exists(self.log.path):
            return []
        out = []
        with open(self.log.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") == "pre_action":
                    d = ev.get("data", {})
                    out.append((d.get("action", ""), d.get("args_digest", "")))
        return out[-n:]

    def _count_actions(self) -> int:
        if not os.path.exists(self.log.path):
            return 0
        n = 0
        with open(self.log.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") == "pre_action":
                    n += 1
        return n

    def _count_missed_predictions(self) -> int:
        """How many of the last 5 post_actions missed their prediction?"""
        if not os.path.exists(self.log.path):
            return 0
        posts = []
        with open(self.log.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") == "post_action":
                    posts.append(ev["data"])
        last5 = posts[-5:]
        return sum(1 for p in last5 if _missed(p.get("predicted", ""), p.get("observed", "")))

    def _confidence_band(self, c) -> Optional[str]:
        if c is None:
            return None
        if c >= 90: return "90-100"
        if c >= 70: return "70-89"
        if c >= 50: return "50-69"
        return "0-49"

    # --- the check ---------------------------------------------------------

    def check(self, action: str, args=None,
              confidence=None, evidence="", on_goal=True,
              reversibility: Optional[str] = None,
              recipients_this_run: Optional[int] = None,
              decision_hint: Optional[str] = None) -> Verdict:

        reversibility = reversibility or self.default_reversibility
        fired: List[dict] = []
        reasons: List[str] = []
        verdict = "green"
        next_action = "proceed"

        # ----- 1. repetition -------------------------------------------------
        recent = self._recent_actions()
        # Add the candidate so the analyzer sees it as the most recent.
        candidate = (action, _digest_str(args))
        loop_report = analyze_loops(recent + [candidate])

        if loop_report["exact_repeats"] >= 3:
            fired.append({"trigger": "exact_repetition",
                          "detail": f"'{action}' repeated {loop_report['exact_repeats']}×"})
            reasons.append(f"exact repetition: '{action}' repeated {loop_report['exact_repeats']}×")
        elif loop_report["exact_repeats"] == 2:
            fired.append({"trigger": "exact_repetition_yellow",
                          "detail": f"'{action}' repeated 2× (1 retry allowed for transient fail)"})
            reasons.append(f"exact repetition 2× — allowed only if first was transient failure")

        if loop_report["semantic_repeats"] >= 3 and "exact_repetition" not in {f["trigger"] for f in fired}:
            fired.append({"trigger": "semantic_repetition",
                          "detail": f"{loop_report['semantic_repeats']} near-identical-intent actions"})
            reasons.append(f"semantic repetition: {loop_report['semantic_repeats']} similar actions")

        if loop_report["oscillation"]:
            fired.append({"trigger": "oscillation",
                          "detail": f"{loop_report['reasons']}"})
            reasons.append("oscillation: A-B-A-B pattern detected")

        # ----- 2. confidence floor -----------------------------------------
        floor = CONFIDENCE_FLOOR.get(reversibility, 50)
        if confidence is not None and confidence < floor:
            fired.append({"trigger": "low_confidence",
                          "detail": f"confidence {confidence} < floor {floor} for {reversibility}"})
            reasons.append(f"confidence {confidence} below floor {floor} for {reversibility} action")

        # Confidence without evidence is treated as low confidence.
        if confidence is not None and confidence >= 70 and not evidence.strip():
            fired.append({"trigger": "confidence_no_evidence",
                          "detail": "stated confidence ≥70 with no evidence clause"})
            reasons.append("confidence ≥70 stated without an evidence clause")

        # Confidence rose after a failure → red flag.
        if confidence is not None:
            band_posts = self._recent_confidence_band_posts()
            if band_posts:
                last_conf = band_posts[-1]
                if confidence > last_conf + 10 and self._count_missed_predictions() > 0:
                    fired.append({"trigger": "confidence_rose_after_failure",
                                  "detail": f"confidence {last_conf}→{confidence} after missed prediction"})
                    reasons.append("confidence rose after a missed prediction (rationalization)")

        # ----- 3. goal drift ------------------------------------------------
        if on_goal is False:
            fired.append({"trigger": "goal_drift",
                          "detail": "agent flagged current action as off-goal"})
            reasons.append("current action does not serve the stated goal")

        # ----- 4. cost / blast-radius --------------------------------------
        if action in ALWAYS_PAUSE_TOOLS:
            fired.append({"trigger": "dangerous_tool",
                          "detail": f"'{action}' is in ALWAYS_PAUSE_TOOLS"})
            reasons.append(f"'{action}' always requires pause & verify regardless of confidence")

        if recipients_this_run is not None and recipients_this_run > self.recipient_cap:
            fired.append({"trigger": "recipient_cap_exceeded",
                          "detail": f"{recipients_this_run} > cap {self.recipient_cap}"})
            reasons.append(f"recipient count {recipients_this_run} exceeds cap {self.recipient_cap}")

        # ----- 5. step budget ----------------------------------------------
        actions_taken = self._count_actions()
        if self.expected_steps:
            mult = actions_taken / max(self.expected_steps, 1)
            if mult >= 4 or (self.hard_step_cap and actions_taken >= self.hard_step_cap):
                fired.append({"trigger": "step_budget_exceeded",
                              "detail": f"actions {actions_taken} ≥ 4× expected {self.expected_steps}"})
                reasons.append(f"step budget: {actions_taken} actions vs {self.expected_steps} expected (4×)")
            elif mult >= YELLOW_AT_STEPS_MULT:
                fired.append({"trigger": "step_budget_warning",
                              "detail": f"actions {actions_taken} ≥ 2× expected {self.expected_steps}"})
                reasons.append(f"step budget warning: {actions_taken} ≥ 2× expected {self.expected_steps}")

        # ----- 6. multi-trigger stacking & "red after a miss" ---------------
        triggers_red = {f["trigger"] for f in fired} & {
            "exact_repetition", "semantic_repetition", "oscillation",
            "low_confidence", "goal_drift", "dangerous_tool",
            "recipient_cap_exceeded", "step_budget_exceeded",
        }
        triggers_yellow = {f["trigger"] for f in fired} & {
            "exact_repetition_yellow", "step_budget_warning", "confidence_no_evidence",
        }
        # Trigger right after a missed prediction = red regardless of individual threshold.
        just_missed = self._count_missed_predictions() > 0
        # Per the discipline: one trigger near threshold → yellow, two → red,
        # trigger after a miss → red.
        if len(triggers_red) >= 1 or (len(triggers_yellow) >= 2) or (fired and just_missed and len(fired) >= 1):
            verdict = "red"
            next_action = "escalate" if any(
                t in {"dangerous_tool", "recipient_cap_exceeded", "goal_drift"}
                for t in {f["trigger"] for f in fired}
            ) else "pause"
        elif fired:
            verdict = "yellow"
            next_action = "proceed_cautious"

        # ----- write the audit trail ---------------------------------------
        # Always log the pre_action so the chain is complete.
        self.log.pre_action(
            action=action,
            args=args,
            confidence=confidence,
            evidence=evidence,
            on_goal=_as_bool(on_goal),
            escalate=(verdict == "red"),
            decision=next_action,
        )
        # Log a trigger event for each fired trigger (so check_run can count them).
        for f in fired:
            self.log.trigger(
                trigger=f["trigger"],
                detail=f["detail"],
                response=("escalate" if verdict == "red"
                          else "proceed_cautious" if verdict == "yellow"
                          else "note"),
                result="",
            )

        return Verdict(verdict=verdict, reasons=reasons,
                       next_action=next_action, fired_triggers=fired)

    # --- post-action helpers -----------------------------------------------

    def observed(self, action, predicted="", observed="",
                 confidence_was=None, confidence_should=None, note=""):
        """Record what actually happened after the action."""
        self.log.post_action(action=action, predicted=predicted, observed=observed,
                             confidence_was=confidence_was,
                             confidence_should=confidence_should, note=note)

    def note(self, text: str):
        self.log.note(text)

    def escalate(self, asked, options=None, recommendation="", answer="", responder=""):
        self.log.escalation(asked=asked, options=options or [],
                            recommendation=recommendation, answer=answer, responder=responder)

    def close(self, status="success", operator_notes=""):
        self.log.close(status=status, operator_notes=operator_notes)

    def _recent_confidence_band_posts(self) -> List[int]:
        if not os.path.exists(self.log.path):
            return []
        out = []
        with open(self.log.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") == "post_action":
                    c = ev["data"].get("confidence_was")
                    if isinstance(c, (int, float)):
                        out.append(int(c))
        return out


def _digest_str(args) -> str:
    if args is None:
        return ""
    try:
        s = _canonical(args) if isinstance(args, (dict, list)) else str(args)
    except Exception:
        s = str(args)
    return s if len(s) <= 120 else s[:117] + "..."


def _missed(predicted: str, observed: str) -> bool:
    p = (predicted or "").lower().strip()
    o = (observed or "").lower().strip()
    if not p and not o:
        return False
    if p == o:
        return False
    if not p or not o:
        return True
    tp, to = set(p.split()), set(o.split())
    if not tp or not to:
        return True
    return len(tp & to) / len(tp | to) < 0.5


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    p = argparse.ArgumentParser(description="Pre-action gate combining the four disciplines.")
    p.add_argument("--action", required=True)
    p.add_argument("--args", default="{}")
    p.add_argument("--goal", default="")
    p.add_argument("--confidence", type=float, default=None)
    p.add_argument("--evidence", default="")
    p.add_argument("--on-goal", default="yes")
    p.add_argument("--reversibility", default="reversible",
                   choices=list(CONFIDENCE_FLOOR.keys()))
    p.add_argument("--recipients-this-run", type=int, default=None)
    p.add_argument("--expected-steps", type=int, default=None)
    p.add_argument("--hard-step-cap", type=int, default=None)
    p.add_argument("--recipient-cap", type=int, default=RECIPIENT_DEFAULT_CAP)
    p.add_argument("--log", default=os.environ.get("INTRINSIC_LOG", "metacog_audit.jsonl"))
    args = p.parse_args()

    g = Guard(log_path=args.log, goal=args.goal,
              expected_steps=args.expected_steps,
              hard_step_cap=args.hard_step_cap,
              recipient_cap=args.recipient_cap,
              reversibility=args.reversibility)

    verdict = g.check(
        action=args.action,
        args=json.loads(args.args) if args.args else None,
        confidence=args.confidence,
        evidence=args.evidence,
        on_goal=_as_bool(args.on_goal),
        reversibility=args.reversibility,
        recipients_this_run=args.recipients_this_run,
    )
    print(json.dumps(verdict.to_dict(), indent=2))
    sys.exit({"green": 0, "yellow": 2, "red": 3}[verdict.verdict])


if __name__ == "__main__":
    main()
