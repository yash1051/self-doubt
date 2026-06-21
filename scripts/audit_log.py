#!/usr/bin/env python3
"""
audit_log.py — tamper-evident, hash-chained audit log for agent runs.

Each event is one JSON line. Each line's hash chains into the next (SHA-256),
so any deletion or edit of a past entry breaks the chain and is detectable by
`verify`. This is what turns a self-audit log into evidence a human (or a
regulator) can stand behind.

Event types: start | pre_action | post_action | trigger | escalation | close | note.
The schema is a superset of the canonical metacog audit schema; v3 adds `note`
events for free-form context.

Usage (CLI):
    python audit_log.py start  --task "..." [--goal "..."] [--expected-steps N]
    python audit_log.py event  --type pre_action --data '{"action":"send"}'
    python audit_log.py close  --status success [--notes "..."]
    python audit_log.py verify
    python audit_log.py tail --n 20

Usage (library):
    from audit_log import AuditLog
    log = AuditLog.start(goal="...", expected_steps=5)
    log.pre_action("send_email", {"to":"a@x"}, confidence=90, evidence="...", on_goal=True)
    log.post_action("send_email", predicted="200", observed="200")
    log.trigger("repetition", "3rd identical send", response="pause", result="deduped")
    log.escalation(asked="...", answer="...", responder="operator")
    log.note("free-form observation")
    log.close(status="success", operator_notes="...")
    ok, problems = log.verify()

Default log path: ./metacog_audit.jsonl  (override with --log or INTRINSIC_LOG env)
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone

DEFAULT_LOG = "metacog_audit.jsonl"
ZERO_HASH = "0" * 64
ALLOWED_TYPES = {"start", "pre_action", "post_action", "trigger",
                 "escalation", "close", "note"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj) -> str:
    """Deterministic JSON for hashing: sorted keys, no whitespace, stable for str/int/float/None/bool."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_event(event_without_hash: dict) -> str:
    return hashlib.sha256(_canonical(event_without_hash).encode("utf-8")).hexdigest()


def _digest(args) -> str:
    if args is None:
        return ""
    try:
        s = _canonical(args) if isinstance(args, (dict, list)) else str(args)
    except Exception:
        s = str(args)
    return s if len(s) <= 120 else s[:117] + "..."


class AuditLog:
    def __init__(self, path: str = DEFAULT_LOG):
        self.path = path

    # ---- internals ---------------------------------------------------------

    def _last(self):
        """Return (last_seq, last_hash) or (-1, ZERO_HASH) for a fresh log."""
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return -1, ZERO_HASH
        last_line = None
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return -1, ZERO_HASH
        obj = json.loads(last_line)
        return obj["seq"], obj["hash"]

    def _append(self, etype: str, data: dict) -> dict:
        if etype not in ALLOWED_TYPES:
            raise ValueError(f"unknown event type: {etype!r}")
        last_seq, last_hash = self._last()
        event = {
            "seq": last_seq + 1,
            "ts": _now(),
            "type": etype,
            "data": data,
            "prev_hash": last_hash,
        }
        event["hash"] = _hash_event(event)
        # Single-writer; flush so a crash after the line lands still has the hash on disk.
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(_canonical(event) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return event

    # ---- public API --------------------------------------------------------

    @classmethod
    def start(cls, goal="", task="", expected_steps=None, stop_conditions="",
              path: str = DEFAULT_LOG):
        log = cls(path)
        run_id = uuid.uuid4().hex[:12]
        log._append("start", {
            "run_id": run_id,
            "task": task,
            "goal": goal or task,
            "expected_steps": expected_steps,
            "stop_conditions": stop_conditions,
        })
        return log

    def pre_action(self, action, args=None, confidence=None, evidence="",
                   on_goal=True, escalate=False, decision="proceed"):
        return self._append("pre_action", {
            "action": action,
            "args_digest": _digest(args),
            "confidence": confidence,
            "evidence": evidence,
            "on_goal": on_goal,
            "escalate": escalate,
            "decision": decision,
        })

    def post_action(self, action, predicted="", observed="",
                    confidence_was=None, confidence_should=None, note=""):
        return self._append("post_action", {
            "action": action,
            "predicted": str(predicted),
            "observed": str(observed),
            "confidence_was": confidence_was,
            "confidence_should": confidence_should,
            "note": note,
        })

    def trigger(self, trigger, detail="", response="", result=""):
        return self._append("trigger", {
            "trigger": trigger,
            "detail": detail,
            "response": response,
            "result": result,
        })

    def escalation(self, asked="", options=None, recommendation="",
                   answer="", responder=""):
        return self._append("escalation", {
            "asked": asked,
            "options": options or [],
            "recommendation": recommendation,
            "answer": answer,
            "responder": responder,
        })

    def note(self, text: str):
        """v3 addition: free-form observation the agent wants preserved verbatim."""
        return self._append("note", {"text": text})

    def close(self, status="success", checks_fired=None, escalations=None,
              operator_notes=""):
        return self._append("close", {
            "status": status,
            "checks_fired": checks_fired,
            "escalations": escalations,
            "operator_notes": operator_notes,
        })

    # ---- verification ------------------------------------------------------

    def verify(self):
        """Walk the chain. Returns (ok: bool, problems: list[str])."""
        problems = []
        prev_hash = ZERO_HASH
        prev_seq = -1
        if not os.path.exists(self.path):
            return False, [f"log not found: {self.path}"]
        with open(self.path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                stated = obj.get("hash")
                recomputed = _hash_event({k: v for k, v in obj.items() if k != "hash"})
                if stated != recomputed:
                    problems.append(f"line {i}: hash mismatch (entry was altered)")
                if obj.get("prev_hash") != prev_hash:
                    problems.append(f"line {i}: broken chain (an entry was removed or reordered)")
                if obj.get("seq") != prev_seq + 1:
                    problems.append(f"line {i}: non-sequential seq {obj.get('seq')} after {prev_seq}")
                if obj.get("type") not in ALLOWED_TYPES:
                    problems.append(f"line {i}: unknown type {obj.get('type')!r}")
                prev_hash = stated
                prev_seq = obj.get("seq", prev_seq)
        return (len(problems) == 0), problems


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _resolve_path(args) -> str:
    return os.environ.get("INTRINSIC_LOG", getattr(args, "log", None) or DEFAULT_LOG)


def main():
    p = argparse.ArgumentParser(description="Tamper-evident agent audit log.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start")
    sp.add_argument("--task", default="")
    sp.add_argument("--goal", default="")
    sp.add_argument("--expected-steps", type=int, default=None)
    sp.add_argument("--stop-conditions", default="")
    sp.add_argument("--log", default=DEFAULT_LOG)

    ep = sub.add_parser("event")
    ep.add_argument("--type", required=True, choices=sorted(ALLOWED_TYPES))
    ep.add_argument("--data", required=True, help="JSON object for this event's data")
    ep.add_argument("--log", default=DEFAULT_LOG)

    cp = sub.add_parser("close")
    cp.add_argument("--status", default="success")
    cp.add_argument("--notes", default="")
    cp.add_argument("--checks-fired", type=int, default=None)
    cp.add_argument("--escalations", type=int, default=None)
    cp.add_argument("--log", default=DEFAULT_LOG)

    vp = sub.add_parser("verify")
    vp.add_argument("--log", default=DEFAULT_LOG)

    tp = sub.add_parser("tail")
    tp.add_argument("--n", type=int, default=20)
    tp.add_argument("--log", default=DEFAULT_LOG)

    args = p.parse_args()

    if args.cmd == "start":
        log = AuditLog.start(goal=args.goal, task=args.task,
                             expected_steps=args.expected_steps,
                             stop_conditions=args.stop_conditions, path=args.log)
        print(f"Started audit log at {log.path}")
    elif args.cmd == "event":
        log = AuditLog(args.log)
        data = json.loads(args.data)
        log._append(args.type, data)
        print(f"Appended {args.type} event.")
    elif args.cmd == "close":
        log = AuditLog(args.log)
        log.close(status=args.status, checks_fired=args.checks_fired,
                  escalations=args.escalations, operator_notes=args.notes)
        print(f"Closed log with status={args.status}.")
    elif args.cmd == "verify":
        ok, problems = AuditLog(args.log).verify()
        if ok:
            print("✅ Chain intact — no tampering detected.")
        else:
            print("❌ Chain verification FAILED:")
            for pr in problems:
                print("  -", pr)
            sys.exit(1)
    elif args.cmd == "tail":
        if not os.path.exists(args.log):
            print(f"(no log at {args.log})")
            return
        with open(args.log, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-args.n:]:
            print(line.rstrip())


if __name__ == "__main__":
    main()
