#!/usr/bin/env python3
"""Deterministic, observer-only repository assurance checks for JLMIRROR.

The validator intentionally has no network access and performs no mutation. It
produces exact-run evidence for a bounded set of mechanically falsifiable
properties. A clean result is evidence for these checks only; it is never
normative approval or merge authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote
import re
import sys

PROFILE_ID = "jlmirror-deterministic-assurance/v1"

WORKFLOW_SUFFIXES = {".yml", ".yaml"}
TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".py", ".json", ".toml", ".txt"}

ACTION_USE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)\s*(?:#.*)?$", re.MULTILINE)
IMMUTABLE_ACTION_RE = re.compile(r"^[^@]+@[0-9a-fA-F]{40}$")
_PERMISSION_KEYS = (
    "actions|attestations|checks|contents|deployments|discussions|id-token|issues|"
    "packages|pages|pull-requests|repository-projects|security-events|statuses"
)
WRITE_PERMISSION_RE = re.compile(
    rf"^\s*(?:{_PERMISSION_KEYS}):\s*write\s*(?:#.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
INLINE_WRITE_PERMISSION_RE = re.compile(
    rf"^\s*permissions:\s*\{{[^}}\n]*\b(?:{_PERMISSION_KEYS})\s*:\s*write\b",
    re.IGNORECASE | re.MULTILINE,
)
WRITE_ALL_RE = re.compile(r"^\s*permissions:\s*write-all\s*(?:#.*)?$", re.IGNORECASE | re.MULTILINE)
PULL_REQUEST_TARGET_RE = re.compile(
    r"^\s*(?:pull_request_target\s*:|on\s*:\s*pull_request_target\s*$|on\s*:\s*\[[^\]]*\bpull_request_target\b[^\]]*\])",
    re.IGNORECASE | re.MULTILINE,
)
SECRET_REFERENCE_RE = re.compile(r"\$\{\{\s*secrets\.", re.IGNORECASE)
SECRET_INHERIT_RE = re.compile(r"^\s*secrets:\s*inherit\s*(?:#.*)?$", re.IGNORECASE | re.MULTILINE)
ENVIRONMENT_RE = re.compile(r"^\s*environment\s*:", re.IGNORECASE | re.MULTILINE)
CONTINUE_ON_ERROR_RE = re.compile(r"^\s*continue-on-error:\s*true\s*(?:#.*)?$", re.IGNORECASE | re.MULTILINE)
UNSAFE_CHECKOUT_TRUE_RE = re.compile(r"^\s*allow-unsafe-pr-checkout:\s*true\s*(?:#.*)?$", re.IGNORECASE | re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)

MUTATING_COMMANDS = [
    (re.compile(r"\bgit\s+push\b", re.IGNORECASE), "git push"),
    (re.compile(r"\bgit\s+commit\b", re.IGNORECASE), "git commit"),
    (re.compile(r"\bgh\s+pr\s+(?:merge|create|close|edit)\b", re.IGNORECASE), "gh pr mutation"),
    (re.compile(r"\bgh\s+issue\s+(?:create|close|edit)\b", re.IGNORECASE), "gh issue mutation"),
    (re.compile(r"\bgh\s+release\s+create\b", re.IGNORECASE), "gh release create"),
    (
        re.compile(
            r"\bgh\s+api\b[^\n]*(?:-X|--method)\s*(?:POST|PUT|PATCH|DELETE)\b",
            re.IGNORECASE,
        ),
        "gh api write method",
    ),
    (
        re.compile(
            r"\bcurl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)\b",
            re.IGNORECASE,
        ),
        "curl write method",
    ),
]


@dataclass(frozen=True)
class Finding:
    path: str
    message: str
    line: int = 1


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _workflow_files(root: Path) -> list[Path]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return []
    return sorted(
        path
        for path in workflow_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in WORKFLOW_SUFFIXES
    )


def _check_workflow_policy(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for path in _workflow_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")

        for regex, message in (
            (WRITE_ALL_RE, "workflow grants permissions: write-all; observer-only workflows must not have canonical mutation authority"),
            (WRITE_PERMISSION_RE, "workflow grants a write permission; the v1 assurance profile is read-only"),
            (INLINE_WRITE_PERMISSION_RE, "workflow grants an inline write permission; the v1 assurance profile is read-only"),
            (PULL_REQUEST_TARGET_RE, "pull_request_target is forbidden in the v1 assurance profile because untrusted PR content must not gain privileged execution context"),
            (SECRET_REFERENCE_RE, "workflow references a GitHub secret; the v1 pull-request assurance profile is secretless"),
            (SECRET_INHERIT_RE, "workflow inherits secrets; the v1 assurance profile is secretless"),
            (ENVIRONMENT_RE, "workflow binds a GitHub environment; v1 does not admit environment-scoped credentials or deployment authority"),
            (CONTINUE_ON_ERROR_RE, "workflow permits continue-on-error; assurance failures must remain job-failing evidence"),
            (UNSAFE_CHECKOUT_TRUE_RE, "workflow enables unsafe pull-request checkout behavior; v1 requires it disabled"),
        ):
            for match in regex.finditer(text):
                findings.append(Finding(rel, message, _line_for_offset(text, match.start())))

        for match in ACTION_USE_RE.finditer(text):
            use = match.group(1)
            if use.startswith("./"):
                continue
            if use.startswith("docker://"):
                findings.append(
                    Finding(
                        rel,
                        "docker action references are not admitted by v1; use a separately reviewed immutable digest policy",
                        _line_for_offset(text, match.start()),
                    )
                )
                continue
            if not IMMUTABLE_ACTION_RE.fullmatch(use):
                findings.append(
                    Finding(
                        rel,
                        f"external action must be pinned to an immutable 40-hex commit SHA: {use}",
                        _line_for_offset(text, match.start()),
                    )
                )

        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "uses: actions/checkout@" not in line:
                continue
            window = "\n".join(lines[index + 1 : index + 16])
            if not re.search(r"^\s*persist-credentials:\s*false\s*(?:#.*)?$", window, re.MULTILINE):
                findings.append(
                    Finding(
                        rel,
                        "actions/checkout must set persist-credentials: false so analysis does not retain push credentials",
                        index + 1,
                    )
                )
            if not re.search(r"^\s*allow-unsafe-pr-checkout:\s*false\s*(?:#.*)?$", window, re.MULTILINE):
                findings.append(
                    Finding(
                        rel,
                        "actions/checkout must explicitly set allow-unsafe-pr-checkout: false in v1",
                        index + 1,
                    )
                )

        for regex, label in MUTATING_COMMANDS:
            for match in regex.finditer(text):
                findings.append(
                    Finding(
                        rel,
                        f"observer-only workflow contains a prohibited mutation command: {label}",
                        _line_for_offset(text, match.start()),
                    )
                )

    return findings


def _clean_link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if not target:
        return None

    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    elif " \"" in target:
        target = target.split(" \"", 1)[0]
    elif " '" in target:
        target = target.split(" '", 1)[0]

    target = unquote(target).strip()
    lower = target.lower()
    if (
        lower.startswith("http://")
        or lower.startswith("https://")
        or lower.startswith("mailto:")
        or lower.startswith("data:")
        or lower.startswith("javascript:")
        or target.startswith("#")
        or target.startswith("${{")
    ):
        return None

    return target.split("#", 1)[0].split("?", 1)[0] or None


def _check_markdown_integrity(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")

        fences = list(FENCE_RE.finditer(text))
        if len(fences) % 2 != 0:
            findings.append(Finding(rel, "unbalanced triple-backtick code fence"))

        for match in MARKDOWN_LINK_RE.finditer(text):
            cleaned = _clean_link_target(match.group(1))
            if cleaned is None:
                continue
            candidate = (path.parent / cleaned).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                findings.append(
                    Finding(
                        rel,
                        f"relative Markdown link escapes repository root: {cleaned}",
                        _line_for_offset(text, match.start()),
                    )
                )
                continue
            if not candidate.exists():
                findings.append(
                    Finding(
                        rel,
                        f"broken relative Markdown link: {cleaned}",
                        _line_for_offset(text, match.start()),
                    )
                )

    return findings


def _check_text_hygiene(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    private_key_labels = (
        "PRIVATE KEY",
        "RSA PRIVATE KEY",
        "EC PRIVATE KEY",
        "OPENSSH PRIVATE KEY",
    )
    private_key_markers = tuple(f"-----BEGIN {label}-----" for label in private_key_labels)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for marker in private_key_markers:
            offset = text.find(marker)
            if offset >= 0:
                findings.append(
                    Finding(
                        rel,
                        "private-key material marker found in repository text",
                        _line_for_offset(text, offset),
                    )
                )

    return findings


def validate_repository(root: Path) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    findings.extend(_check_workflow_policy(root))
    findings.extend(_check_markdown_integrity(root))
    findings.extend(_check_text_hygiene(root))
    return sorted(findings, key=lambda item: (item.path, item.line, item.message))


def _escape_annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")
    findings = validate_repository(root)

    print(f"JLMIRROR deterministic assurance profile: {PROFILE_ID}")
    print(f"Repository root: {root.resolve()}")
    print(f"Python runtime: {sys.version.split()[0]}")

    if not findings:
        print("RESULT: PASS — no findings in the deterministic v1 coverage set")
        print("NOTE: PASS is evidence only; it is not Native Assurance, acceptance, or merge authorization.")
        return 0

    print(f"RESULT: FAIL — {len(findings)} finding(s)")
    for finding in findings:
        print(
            f"::error file={_escape_annotation(finding.path)},line={finding.line}::"
            f"{_escape_annotation(finding.message)}"
        )
        print(f"- {finding.path}:{finding.line}: {finding.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
