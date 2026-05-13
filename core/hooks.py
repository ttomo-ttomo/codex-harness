#!/usr/bin/env python3
"""Hook entry points for Claude Code.

Usage:
    python3 core/hooks.py pre    # PreToolUse
    python3 core/hooks.py post   # PostToolUse
    python3 core/hooks.py stop   # Stop

Protocol (Claude Code):
    - stdin: JSON payload describing the event
    - stderr: human-readable reason or summary
    - exit 0: allow
    - exit 2: block (PreToolUse only)

Fail open: any uncaught error exits 0 so a harness bug never bricks the agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `python3 core/hooks.py ...` without setting PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from domain import parse_event
from engine import TRACE_PATH, EvaluationResult, evaluate, write_trace
from rules import ALL_RULES, POST_RULES


def _read_event() -> dict | None:
    try:
        return json.loads(sys.stdin.read())
    except Exception as err:
        sys.stderr.write(f"[harness-core] Invalid JSON from stdin: {err}\n")
        return None


def _emit_warnings(result: EvaluationResult) -> None:
    for r in result.reasons:
        sys.stderr.write(f"[{r['ruleId']}] {r['reason']}\n")


def run_pre() -> int:
    raw = _read_event()
    if raw is None:
        return 0
    call = parse_event(raw)
    result = evaluate(ALL_RULES, call)
    write_trace(call, result)

    if result.action == "deny":
        msg = "\n".join(f"[{r['ruleId']}] {r['reason']}" for r in result.reasons)
        sys.stderr.write(msg + "\n")
        return 2
    if result.action == "warn":
        _emit_warnings(result)
    return 0


def run_post() -> int:
    raw = _read_event()
    if raw is None:
        return 0
    call = parse_event(raw)
    result = evaluate(POST_RULES, call)
    write_trace(call, result)
    if result.action == "warn":
        _emit_warnings(result)
    return 0


def run_stop() -> int:
    raw = _read_event()
    if raw is None:
        return 0
    call = parse_event(raw)
    if call.event != "Stop":
        return 0

    write_trace(call)

    if not TRACE_PATH.exists():
        return 0

    writes = bashes = warns = denies = 0
    with TRACE_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("session_id") != call.session_id:
                continue
            tool = rec.get("tool")
            if tool in ("Write", "Edit"):
                writes += 1
            elif tool == "Bash":
                bashes += 1
            if rec.get("decision") == "warn":
                warns += 1
            elif rec.get("decision") == "deny":
                denies += 1

    sys.stderr.write(
        f"[harness-core] Session summary: {writes} file edits, {bashes} bash commands, "
        f"{warns} warnings, {denies} denials. Trace: {TRACE_PATH}\n"
    )
    return 0


_DISPATCH = {"pre": run_pre, "post": run_post, "stop": run_stop}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in _DISPATCH:
        sys.stderr.write("usage: hooks.py {pre|post|stop}\n")
        return 0
    try:
        return _DISPATCH[sys.argv[1]]()
    except Exception as err:
        # Fail open: do not block the agent on our own bug.
        sys.stderr.write(f"[harness-core] {sys.argv[1]} crashed: {err}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
