"""Codex CLI detection and fallback helpers.

Public API:
    detect_codex(timeout, force) -> CodexDetectionResult
    should_fallback(setting) -> tuple[bool, str]
    read_setting() -> str
    format_fallback_marker(reason, strategy) -> str

Strategy names returned by should_fallback (second tuple element):
    "codex-native"     — Codex available, do not fall back
    "claude-subagent"  — Codex unavailable (or forced); use Claude subagent
    "off"              — fallback disabled; caller must hard-stop if Codex absent

format_fallback_marker MUST only be invoked when should_fallback returned
fallback==True (the marker text claims "Codex unavailable" — calling it
otherwise would emit a false statement). The marker format is the canonical
source for ADR-0001 secondary decision 3; do not duplicate the string elsewhere.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

_DEFAULT_SETTING = "auto"
_ENV_VAR = "CODEX_HARNESS_FALLBACK"
_VALID_SETTINGS = {"auto", "off", "claude-subagent"}


@dataclass(frozen=True)
class CodexDetectionResult:
    available: bool
    version: str | None
    reason: str | None


_CACHE: dict[float, CodexDetectionResult] = {}


def detect_codex(timeout: float = 2.0, force: bool = False) -> CodexDetectionResult:
    cache_key = timeout
    if not force and cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        completed = subprocess.run(
            ["codex", "--version"],
            timeout=timeout,
            shell=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        result = CodexDetectionResult(
            available=False,
            version=None,
            reason="not found: codex binary not on PATH",
        )
        _CACHE[cache_key] = result
        return result
    except subprocess.TimeoutExpired:
        result = CodexDetectionResult(
            available=False,
            version=None,
            reason=f"timeout after {timeout}s",
        )
        _CACHE[cache_key] = result
        return result
    except OSError as err:
        result = CodexDetectionResult(
            available=False,
            version=None,
            reason=f"OSError: {type(err).__name__}",
        )
        _CACHE[cache_key] = result
        return result
    except Exception as err:
        # Detection must degrade gracefully because it gates fallback behavior.
        result = CodexDetectionResult(
            available=False,
            version=None,
            reason=f"unexpected: {type(err).__name__}",
        )
        _CACHE[cache_key] = result
        return result

    if completed.returncode != 0:
        result = CodexDetectionResult(
            available=False,
            version=None,
            reason=f"non-zero exit: {completed.returncode}",
        )
        _CACHE[cache_key] = result
        return result

    result = CodexDetectionResult(
        available=True,
        version=_parse_version(completed.stdout),
        reason=None,
    )
    _CACHE[cache_key] = result
    return result


def should_fallback(setting: str | None = None) -> tuple[bool, str]:
    normalized = read_setting() if setting is None else _normalize_setting(setting)

    if normalized == "off":
        return False, "off"

    if normalized == "claude-subagent":
        return True, "claude-subagent"

    detection = detect_codex()
    if detection.available:
        return False, "codex-native"
    return True, "claude-subagent"


def read_setting() -> str:
    raw = os.environ.get(_ENV_VAR)
    if raw is None:
        return _DEFAULT_SETTING

    normalized = raw.strip().lower()
    if normalized == "":
        return _DEFAULT_SETTING
    if normalized in _VALID_SETTINGS:
        return normalized

    sys.stderr.write(
        f"[harness-core] Invalid {_ENV_VAR}={raw}, falling back to 'auto'.\n"
    )
    return _DEFAULT_SETTING


def format_fallback_marker(reason: str, strategy: str) -> str:
    return (
        "[harness-core] FALLBACK MODE: "
        f"Codex unavailable ({reason}). Strategy: {strategy}. Quality may degrade."
    )


def _normalize_setting(setting: str) -> str:
    normalized = setting.strip().lower()
    if normalized == "":
        return _DEFAULT_SETTING
    if normalized in _VALID_SETTINGS:
        return normalized
    # Mirror read_setting()'s warning so direct should_fallback(setting=...) calls
    # do not silently swallow bogus input.
    sys.stderr.write(
        f"[harness-core] Invalid setting={setting!r}, falling back to {_DEFAULT_SETTING!r}.\n"
    )
    return _DEFAULT_SETTING


def _parse_version(stdout: str) -> str:
    cleaned = stdout.strip()
    if cleaned == "":
        return cleaned

    parts = cleaned.split()
    if len(parts) < 2:
        return cleaned
    return parts[-1]
