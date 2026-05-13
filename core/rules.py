"""Guardrail rules.

Simple pattern rules are declared via `bash_pattern_rule` / `path_pattern_rule`.
Rules with branching logic (R09, POST-01) define their own `check`.

R01-R04: Universal denials — always block.
R05-R09: Mode-specific — context-dependent.
POST-01: Post-tool warnings — allow but flag.

Rule IDs are stable. Never renumber.
"""

from __future__ import annotations

import re

from domain import (
    ALLOW,
    Decision,
    Rule,
    ToolCall,
    bash_pattern_rule,
    path_pattern_rule,
)


# ---------------------------------------------------------------------------
# R01: Deny sudo
# ---------------------------------------------------------------------------

R01_NO_SUDO = bash_pattern_rule(
    id="R01",
    description="Deny sudo commands",
    action="deny",
    patterns=[r"(^|\s|;|&&|\|\|)sudo\b"],
    message="R01: sudo is not permitted. Request manual execution if truly required.",
)


# ---------------------------------------------------------------------------
# R02: Deny writes to secrets and version control internals
# ---------------------------------------------------------------------------

R02_PROTECT_SECRETS = path_pattern_rule(
    id="R02",
    description="Deny writes to .git internals, .env, secrets, and key material",
    action="deny",
    patterns=[
        r"(^|/)\.git(/|$)",
        r"(^|/)\.env(\.|$)",
        r"(^|/)\.aws/",
        r"(^|/)\.ssh/",
        r"(^|/)id_(rsa|ed25519|ecdsa)(\.|$)",
        r"(^|/)credentials(\.|$)",
        r"\.pem$",
        r"\.key$",
    ],
    message=lambda call, pat: (
        f"R02: Writes to protected path ({call.path}) are not permitted. Pattern: {pat.pattern}"
    ),
)


# ---------------------------------------------------------------------------
# R03: Deny destructive filesystem operations
# ---------------------------------------------------------------------------

R03_NO_DESTRUCTIVE = bash_pattern_rule(
    id="R03",
    description="Deny destructive filesystem and device operations",
    action="deny",
    patterns=[
        r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+/(\s|$)",
        r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+~\s*(\s|$)",
        r"\bmkfs\b",
        r"\bdd\s+.*of=/dev/(sd|nvme|hd)",
        r"\b:\(\)\s*\{\s*:\|:&\s*\}\s*;:",  # fork bomb
    ],
    message=lambda call, pat: f"R03: Destructive command blocked. Pattern: {pat.pattern}",
)


# ---------------------------------------------------------------------------
# R04: Deny force push and history rewrites
# ---------------------------------------------------------------------------

R04_NO_FORCE_PUSH = bash_pattern_rule(
    id="R04",
    description="Deny force push and destructive history operations",
    action="deny",
    patterns=[
        r"\bgit\s+push\b.*\s(--force|-f)(\s|$)",
        r"\bgit\s+push\b.*\s--force-with-lease\b",
        r"\bgit\s+reset\s+--hard\s+(HEAD~|origin/)",
    ],
    message="R04: Force push or history rewrite blocked. Use a feature branch and PR instead.",
)


# ---------------------------------------------------------------------------
# R05: Warn on package installs without lockfile
# ---------------------------------------------------------------------------


def _r05_check(call: ToolCall) -> Decision:
    if call.command is None:
        return ALLOW
    if re.search(r"\bnpm\s+install\b", call.command) and not re.search(
        r"\bnpm\s+ci\b", call.command
    ):
        return Decision(
            "warn",
            "R05: Prefer `npm ci` for reproducible installs. Use `npm install` only when intentionally updating lockfile.",
        )
    return ALLOW


R05_LOCKFILE_REQUIRED = Rule(
    "R05",
    "Warn when installing packages without a lockfile-aware command",
    ("PreToolUse",),
    _r05_check,
)


# ---------------------------------------------------------------------------
# R06: Warn on production environment references
# ---------------------------------------------------------------------------

R06_PRODUCTION_GUARD = bash_pattern_rule(
    id="R06",
    description="Warn when commands reference production environments",
    action="warn",
    patterns=[re.compile(r"(NODE_ENV=production|ENV=prod|--env[= ]prod|@prod|-prod-)", re.IGNORECASE)],
    message="R06: Command references a production environment. Verify the target is correct.",
)


# ---------------------------------------------------------------------------
# R07: Warn on CI/infrastructure config changes
# ---------------------------------------------------------------------------

R07_INFRA_WARNING = path_pattern_rule(
    id="R07",
    description="Warn on changes to CI workflows and infrastructure-as-code",
    action="warn",
    patterns=[
        r"(^|/)\.github/workflows/",
        r"(^|/)\.gitlab-ci\.yml$",
        r"(^|/)Dockerfile(\.|$)",
        r"(^|/)terraform/",
        r"\.tf$",
    ],
    message=lambda call, pat: (
        f"R07: Modifying infrastructure config ({call.path}). Ensure change is covered by an ADR or task-note."
    ),
)


# ---------------------------------------------------------------------------
# R08: Deny direct writes to lockfiles
# ---------------------------------------------------------------------------

R08_NO_LOCKFILE_EDIT = path_pattern_rule(
    id="R08",
    description="Deny direct edits to lockfiles. Let package managers regenerate them.",
    action="deny",
    patterns=[
        r"(^|/)package-lock\.json$",
        r"(^|/)pnpm-lock\.yaml$",
        r"(^|/)yarn\.lock$",
        r"(^|/)poetry\.lock$",
        r"(^|/)Cargo\.lock$",
        r"(^|/)go\.sum$",
    ],
    message=lambda call, pat: (
        f"R08: Do not edit lockfiles directly ({call.path}). Use the package manager to regenerate."
    ),
)


# ---------------------------------------------------------------------------
# R09: Warn on large-scale deletes
# ---------------------------------------------------------------------------

_RECURSIVE_RM_RE = re.compile(r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\s+[^/~\s][^\s]+")
_FIND_DELETE_RE = re.compile(r"\bfind\s+[^|]*-delete\b")


def _r09_check(call: ToolCall) -> Decision:
    if call.command is None:
        return ALLOW
    if _RECURSIVE_RM_RE.search(call.command):
        return Decision(
            "warn",
            "R09: Recursive delete detected. Confirm scope is intentional before running.",
        )
    if _FIND_DELETE_RE.search(call.command):
        return Decision(
            "warn",
            "R09: `find -delete` can remove many files. Dry-run first without -delete.",
        )
    return ALLOW


R09_BULK_DELETE_WARNING = Rule(
    "R09", "Warn when commands delete many files at once", ("PreToolUse",), _r09_check
)


# ---------------------------------------------------------------------------
# R10: Deny curl/wget piped to a shell
# ---------------------------------------------------------------------------

R10_NO_PIPE_TO_SHELL = bash_pattern_rule(
    id="R10",
    description="Deny curl/wget output piped directly to a shell (supply-chain risk)",
    action="deny",
    patterns=[
        # curl/wget ... | (sudo )?{sh|bash|zsh|fish|ash|dash}
        r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(sh|bash|zsh|fish|ash|dash)\b",
    ],
    message=(
        "R10: Piping curl/wget output to a shell is denied. "
        "Download to a file, inspect, then execute."
    ),
)


# ---------------------------------------------------------------------------
# R11: Deny git operations that bypass hooks or signing
# ---------------------------------------------------------------------------

R11_NO_GIT_BYPASS = bash_pattern_rule(
    id="R11",
    description="Deny git operations that skip hooks (--no-verify) or signing (--no-gpg-sign)",
    action="deny",
    patterns=[
        r"\bgit\s+.*--no-verify\b",
        r"\bgit\s+.*--no-gpg-sign\b",
    ],
    message=lambda call, pat: (
        f"R11: Git hook/signing bypass blocked. "
        f"Fix the underlying failure instead of skipping the check. ({pat.pattern})"
    ),
)


# ---------------------------------------------------------------------------
# POST-01: Warn on test tampering
# ---------------------------------------------------------------------------

_TEST_FILE_PATTERNS = [
    re.compile(r"\.(test|spec)\.(ts|tsx|js|jsx|py)$"),
    re.compile(r"_test\.(py|go)$"),
    re.compile(r"/tests?/"),
]

_TAMPER_SIGNALS = [
    re.compile(r"\bit\.skip\b"),
    re.compile(r"\btest\.skip\b"),
    re.compile(r"\bdescribe\.skip\b"),
    re.compile(r"\bxit\b"),
    re.compile(r"\bxdescribe\b"),
    re.compile(r"@pytest\.mark\.skip"),
    re.compile(r"t\.Skip\("),
]


def _post01_check(call: ToolCall) -> Decision:
    if call.path is None or call.content is None:
        return ALLOW
    if not any(p.search(call.path) for p in _TEST_FILE_PATTERNS):
        return ALLOW
    for signal in _TAMPER_SIGNALS:
        if signal.search(call.content):
            return Decision(
                "warn",
                f"POST-01: Test tamper signal detected in {call.path}. Signal: {signal.pattern}. Verify intent.",
            )
    return ALLOW


POST_01_TEST_TAMPER = Rule(
    "POST-01",
    "Warn when test files are modified to skip or disable assertions",
    ("PostToolUse",),
    _post01_check,
)


# ---------------------------------------------------------------------------
# POST-02: Warn when governance documents are modified
# ---------------------------------------------------------------------------

POST_02_GOVERNANCE_DOCS = path_pattern_rule(
    id="POST-02",
    description="Warn when AGENTS.md / CLAUDE.md / ADRs are modified",
    action="warn",
    events=("PostToolUse",),
    patterns=[
        r"(^|/)AGENTS\.md$",
        r"(^|/)CLAUDE\.md$",
        r"(^|/)docs/adr/.*\.md$",
    ],
    message=lambda call, pat: (
        f"POST-02: Governance doc modified ({call.path}). "
        "Surface this change in the PR or task-note for review."
    ),
)


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

UNIVERSAL_RULES: tuple[Rule, ...] = (
    R01_NO_SUDO,
    R02_PROTECT_SECRETS,
    R03_NO_DESTRUCTIVE,
    R04_NO_FORCE_PUSH,
    R10_NO_PIPE_TO_SHELL,
    R11_NO_GIT_BYPASS,
)

MODE_SPECIFIC_RULES: tuple[Rule, ...] = (
    R05_LOCKFILE_REQUIRED,
    R06_PRODUCTION_GUARD,
    R07_INFRA_WARNING,
    R08_NO_LOCKFILE_EDIT,
    R09_BULK_DELETE_WARNING,
)

POST_RULES: tuple[Rule, ...] = (POST_01_TEST_TAMPER, POST_02_GOVERNANCE_DOCS)

ALL_RULES: tuple[Rule, ...] = UNIVERSAL_RULES + MODE_SPECIFIC_RULES + POST_RULES
