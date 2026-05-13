"""Rule evaluation engine and agent trace logger.

evaluate(rules, call):
    First "deny" decision wins and short-circuits. All "warn" decisions are
    collected. If no deny and no warn, the result is "allow".

write_trace(call, result):
    Append a one-line JSON record to .claude/state/agent-trace.jsonl.
    Used for post-mortem auditing of what the agent actually did.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from domain import Rule, ToolCall

TRACE_PATH = Path(".claude/state/agent-trace.jsonl")

_COMMAND_PREVIEW_LIMIT = 200


@dataclass
class EvaluationResult:
    action: str  # "allow" | "warn" | "deny"
    reasons: list[dict[str, str]] = field(default_factory=list)


def evaluate(rules: Iterable[Rule], call: ToolCall) -> EvaluationResult:
    warnings: list[dict[str, str]] = []

    for rule in rules:
        if call.event not in rule.events:
            continue
        try:
            decision = rule.check(call)
        except Exception as err:
            # A buggy rule must never brick the agent loop.
            sys.stderr.write(f"[harness-core] Rule {rule.id} threw: {err}\n")
            continue

        if decision.action == "deny":
            return EvaluationResult(
                action="deny",
                reasons=[
                    *warnings,
                    {"ruleId": rule.id, "reason": decision.reason or rule.description},
                ],
            )
        if decision.action == "warn":
            warnings.append(
                {"ruleId": rule.id, "reason": decision.reason or rule.description}
            )

    return EvaluationResult(action="warn" if warnings else "allow", reasons=warnings)


def _summarize(call: ToolCall) -> dict[str, Any]:
    if call.event == "Stop":
        return {"summary": "session stop"}

    if call.tool is None:
        return {"summary": call.event or "unknown"}

    if call.path is not None:
        return {"tool": call.tool, "summary": f"{call.tool} {call.path}", "path": call.path}

    if call.command is not None:
        cmd = call.command
        if len(cmd) > _COMMAND_PREVIEW_LIMIT:
            cmd = cmd[:_COMMAND_PREVIEW_LIMIT] + "…"
        return {"tool": call.tool, "summary": f"{call.tool}: {cmd}", "command": cmd}

    return {"tool": call.tool, "summary": call.tool}


def write_trace(call: ToolCall, result: EvaluationResult | None = None) -> None:
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "session_id": call.session_id,
            "event": call.event,
            **_summarize(call),
        }
        if result is not None:
            entry["decision"] = result.action
            if result.reasons:
                entry["decision_reasons"] = result.reasons
        with TRACE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as err:
        # Tracing failures must never break the agent.
        sys.stderr.write(f"[harness-core] Trace write failed: {err}\n")
