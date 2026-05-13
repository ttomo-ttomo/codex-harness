"""Domain types and rule factories.

`ToolCall` normalizes the Claude Code hook payload so rules never touch the
raw dict. If the hook protocol changes, only `parse_event` must update.

Rule factories (`bash_pattern_rule`, `path_pattern_rule`) let simple
pattern-based rules be declared as data. Rules with branching logic
(POST-01, R09) define their own `check` function.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, NamedTuple


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


class Decision(NamedTuple):
    action: str  # "allow" | "warn" | "deny"
    reason: str | None = None


ALLOW = Decision("allow")


# ---------------------------------------------------------------------------
# ToolCall — normalized hook payload
# ---------------------------------------------------------------------------


_WRITE_TOOLS = ("Write", "Edit")


@dataclass(frozen=True)
class ToolCall:
    event: str             # "PreToolUse" | "PostToolUse" | "Stop" | ...
    session_id: str
    tool: str | None       # None for non-tool events (Stop)
    command: str | None    # Bash command, or None
    path: str | None       # Write/Edit target path, or None
    content: str | None    # Written content / new_string, or None


def _coerce_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def parse_event(raw: dict[str, Any]) -> ToolCall:
    """Convert a raw Claude Code hook payload to a `ToolCall`.

    The only place in the codebase that knows the raw hook schema.
    """
    tool = _coerce_str(raw.get("tool_name"))
    tool_input = raw.get("tool_input") if isinstance(raw.get("tool_input"), dict) else {}
    tool_response = raw.get("tool_response") if isinstance(raw.get("tool_response"), dict) else {}

    command = _coerce_str(tool_input.get("command")) if tool == "Bash" else None

    path: str | None = None
    if tool in _WRITE_TOOLS:
        path = _coerce_str(tool_input.get("file_path")) or _coerce_str(tool_input.get("path"))

    content = (
        _coerce_str(tool_input.get("content"))
        or _coerce_str(tool_input.get("new_string"))
        or _coerce_str(tool_response.get("content"))
    )

    return ToolCall(
        event=str(raw.get("hook_event_name", "")),
        session_id=str(raw.get("session_id", "")),
        tool=tool,
        command=command,
        path=path,
        content=content,
    )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    events: tuple[str, ...]
    check: Callable[[ToolCall], Decision]


# ---------------------------------------------------------------------------
# Matchers / factories
# ---------------------------------------------------------------------------

_Patterns = Iterable[str | re.Pattern[str]]
_Message = str | Callable[[ToolCall, re.Pattern[str]], str]


def _compile(patterns: _Patterns) -> tuple[re.Pattern[str], ...]:
    return tuple(p if isinstance(p, re.Pattern) else re.compile(p) for p in patterns)


def _render(message: _Message, call: ToolCall, pat: re.Pattern[str]) -> str:
    return message(call, pat) if callable(message) else message


def bash_pattern_rule(
    *,
    id: str,
    description: str,
    action: str,
    patterns: _Patterns,
    message: _Message,
) -> Rule:
    """Match a Bash command against any of `patterns`; first hit wins."""
    compiled = _compile(patterns)

    def check(call: ToolCall) -> Decision:
        if call.command is None:
            return ALLOW
        for pat in compiled:
            if pat.search(call.command):
                return Decision(action, _render(message, call, pat))
        return ALLOW

    return Rule(id, description, ("PreToolUse",), check)


def path_pattern_rule(
    *,
    id: str,
    description: str,
    action: str,
    patterns: _Patterns,
    message: _Message,
    events: tuple[str, ...] = ("PreToolUse",),
) -> Rule:
    """Match a Write/Edit target path against any of `patterns`."""
    compiled = _compile(patterns)

    def check(call: ToolCall) -> Decision:
        if call.path is None:
            return ALLOW
        for pat in compiled:
            if pat.search(call.path):
                return Decision(action, _render(message, call, pat))
        return ALLOW

    return Rule(id, description, events, check)
