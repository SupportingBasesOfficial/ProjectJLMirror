#!/usr/bin/env python3
"""Deterministic repository assurance checks for JLMIRROR.

The default assurance profile is observer-only. One narrowly scoped workflow may
publish reconciliation commit statuses, but its write-capable jobs must never
checkout or execute pull-request-controlled content and its GitHub API writes are
validated as exact parsed commands rather than substring matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote
import re
import shlex
import sys

PROFILE_ID = "jlmirror-deterministic-assurance/v1"
WORKFLOW_SUFFIXES = {".yml", ".yaml"}
TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".py", ".json", ".toml", ".txt"}
STATUS_PUBLISHER_WORKFLOW = ".github/workflows/adversarial-learning-reconciliation.yml"
EXPECTED_STATUS_ENDPOINT = "repos/${GITHUB_REPOSITORY}/statuses/${PR_HEAD_SHA}"

ACTION_USE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)\s*(?:#.*)?$", re.MULTILINE)
IMMUTABLE_ACTION_RE = re.compile(r"^[^@]+@[0-9a-fA-F]{40}$")
_PERMISSION_KEYS = (
    "actions|attestations|checks|contents|deployments|discussions|id-token|issues|"
    "packages|pages|pull-requests|repository-projects|security-events|statuses"
)
WRITE_PERMISSION_RE = re.compile(rf"^\s*(?:{_PERMISSION_KEYS}):\s*write\s*(?:#.*)?$", re.IGNORECASE | re.MULTILINE)
INLINE_WRITE_PERMISSION_RE = re.compile(rf"^\s*permissions:\s*\{{[^}}\n]*\b(?:{_PERMISSION_KEYS})\s*:\s*write\b", re.IGNORECASE | re.MULTILINE)
WRITE_ALL_RE = re.compile(r"^\s*permissions:\s*write-all\s*(?:#.*)?$", re.IGNORECASE | re.MULTILINE)
PULL_REQUEST_TARGET_RE = re.compile(r"^\s*(?:pull_request_target\s*:|on\s*:\s*pull_request_target\s*$|on\s*:\s*\[[^\]]*\bpull_request_target\b[^\]]*\])", re.IGNORECASE | re.MULTILINE)
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
    (re.compile(r"\bcurl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)\b", re.IGNORECASE), "curl write method"),
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
    return sorted(path for path in workflow_dir.rglob("*") if path.is_file() and path.suffix.lower() in WORKFLOW_SUFFIXES)


def _job_block(text: str, name: str) -> str | None:
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line == f"  {name}:":
            start = idx
            break
    if start is None:
        return None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if re.fullmatch(r"  [A-Za-z0-9_-]+:\s*", lines[idx]):
            end = idx
            break
    return "\n".join(lines[start:end])


def _logical_shell_commands(text: str) -> list[str]:
    commands: list[str] = []
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                commands.append(current.strip())
                current = ""
            continue
        if current:
            current += " " + line
        else:
            current = line
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        commands.append(current.strip())
        current = ""
    if current:
        commands.append(current.strip())
    return commands


def _parse_gh_api(command: str) -> tuple[str, str | None] | None:
    try:
        tokens = shlex.split(command, comments=True, posix=True)
    except ValueError:
        return None
    try:
        gh_index = tokens.index("gh")
    except ValueError:
        return None
    if gh_index + 1 >= len(tokens) or tokens[gh_index + 1] != "api":
        return None
    args = tokens[gh_index + 2 :]
    method = "GET"
    endpoint: str | None = None
    implicit_post = False
    options_with_value = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input", "--jq", "-q", "--header", "-H", "--hostname"}
    idx = 0
    while idx < len(args):
        token = args[idx]
        if token.startswith("--method="):
            method = token.split("=", 1)[1].upper()
        elif token in {"-X", "--method"} and idx + 1 < len(args):
            method = args[idx + 1].upper()
            idx += 1
        elif token in {"-f", "-F", "--field", "--raw-field", "--input"}:
            implicit_post = True
            if idx + 1 < len(args):
                idx += 1
        elif any(token.startswith(prefix + "=") for prefix in ("--field", "--raw-field", "--input")):
            implicit_post = True
        elif token in options_with_value and idx + 1 < len(args):
            idx += 1
        elif not token.startswith("-") and endpoint is None:
            endpoint = token
        idx += 1
    if method == "GET" and implicit_post:
        method = "POST"
    return method, endpoint


def _status_publisher_policy_errors(text: str) -> list[str]:
    errors: list[str] = []
    if "workflow_dispatch:" in text:
        errors.append("status reconciliation workflow must not advertise unsupported workflow_dispatch execution")
    if "cancel-in-progress: true" not in text or "group: adversarial-learning-${{ github.event.issue.number }}" not in text:
        errors.append("status reconciliation must serialize/cancel superseded runs per pull request")
    if not re.search(r"^permissions:\s*\{\}\s*$", text, re.MULTILINE):
        errors.append("status reconciliation must default to zero workflow-level permissions")

    publisher_names = ("publish-pending", "publish-final")
    publisher_blocks: list[str] = []
    for name in publisher_names:
        block = _job_block(text, name)
        if block is None:
            errors.append(f"status reconciliation missing privileged job {name}")
            continue
        publisher_blocks.append(block)
        if block.count("statuses: write") != 1:
            errors.append(f"{name} must grant exactly statuses: write")
        forbidden = ("actions/checkout@", "python3 ", "git ", "$GITHUB_PATH", "$GITHUB_ENV", "source ")
        if any(marker in block for marker in forbidden):
            errors.append(f"{name} must never checkout, source, or execute pull-request-controlled content")
        if "needs.resolve.outputs.pr_head_sha" not in block:
            errors.append(f"{name} must publish only to the trusted resolve-job PR head output")

    analyze = _job_block(text, "analyze")
    if analyze is None:
        errors.append("status reconciliation missing read-only analyze job")
    elif "statuses: write" in analyze:
        errors.append("pull-request analysis job must not receive status-write authority")
    resolve = _job_block(text, "resolve")
    if resolve is None:
        errors.append("status reconciliation missing trusted resolve job")
    elif "statuses: write" in resolve:
        errors.append("PR-head resolution job must not receive status-write authority")

    if len(list(WRITE_PERMISSION_RE.finditer(text))) != 2:
        errors.append("status reconciliation may contain exactly two write permissions, both statuses: write")
    if any(match.group(0).strip().lower() != "statuses: write" for match in WRITE_PERMISSION_RE.finditer(text)):
        errors.append("status reconciliation may not grant any write permission other than statuses: write")
    if INLINE_WRITE_PERMISSION_RE.search(text) or WRITE_ALL_RE.search(text):
        errors.append("status reconciliation may not use inline write permissions or write-all")

    writes: list[tuple[str, str | None]] = []
    for command in _logical_shell_commands(text):
        parsed = _parse_gh_api(command)
        if parsed is None:
            continue
        method, endpoint = parsed
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            writes.append((method, endpoint))
    if writes != [("POST", EXPECTED_STATUS_ENDPOINT), ("POST", EXPECTED_STATUS_ENDPOINT)]:
        errors.append("status reconciliation must perform exactly two parsed POSTs to the exact resolved PR-head status endpoint")
    return errors


def _check_workflow_policy(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in _workflow_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        is_status_publisher = rel == STATUS_PUBLISHER_WORKFLOW

        if is_status_publisher:
            findings.extend(Finding(rel, message) for message in _status_publisher_policy_errors(text))
        else:
            for regex, message in (
                (WRITE_ALL_RE, "workflow grants permissions: write-all; observer-only workflows must not have canonical mutation authority"),
                (WRITE_PERMISSION_RE, "workflow grants a write permission; the v1 assurance profile is read-only"),
                (INLINE_WRITE_PERMISSION_RE, "workflow grants an inline write permission; the v1 assurance profile is read-only"),
            ):
                for match in regex.finditer(text):
                    findings.append(Finding(rel, message, _line_for_offset(text, match.start())))

        for regex, message in (
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
                findings.append(Finding(rel, "docker action references are not admitted by v1; use a separately reviewed immutable digest policy", _line_for_offset(text, match.start())))
            elif not IMMUTABLE_ACTION_RE.fullmatch(use):
                findings.append(Finding(rel, f"external action must be pinned to an immutable 40-hex commit SHA: {use}", _line_for_offset(text, match.start())))

        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "uses: actions/checkout@" not in line:
                continue
            window = "\n".join(lines[index + 1 : index + 16])
            if not re.search(r"^\s*persist-credentials:\s*false\s*(?:#.*)?$", window, re.MULTILINE):
                findings.append(Finding(rel, "actions/checkout must set persist-credentials: false so analysis does not retain push credentials", index + 1))
            if not re.search(r"^\s*allow-unsafe-pr-checkout:\s*false\s*(?:#.*)?$", window, re.MULTILINE):
                findings.append(Finding(rel, "actions/checkout must explicitly set allow-unsafe-pr-checkout: false in v1", index + 1))

        for regex, label in MUTATING_COMMANDS:
            for match in regex.finditer(text):
                findings.append(Finding(rel, f"observer-only workflow contains a prohibited mutation command: {label}", _line_for_offset(text, match.start())))

        if not is_status_publisher:
            for command in _logical_shell_commands(text):
                parsed = _parse_gh_api(command)
                if parsed is not None and parsed[0] in {"POST", "PUT", "PATCH", "DELETE"}:
                    findings.append(Finding(rel, "observer-only workflow contains a prohibited GitHub API mutation"))
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
    if lower.startswith(("http://", "https://", "mailto:", "data:", "javascript:")) or target.startswith("#") or target.startswith("${{"):
        return None
    return target.split("#", 1)[0].split("?", 1)[0] or None


def _check_markdown_integrity(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if len(list(FENCE_RE.finditer(text))) % 2 != 0:
            findings.append(Finding(rel, "unbalanced triple-backtick code fence"))
        for match in MARKDOWN_LINK_RE.finditer(text):
            cleaned = _clean_link_target(match.group(1))
            if cleaned is None:
                continue
            candidate = (path.parent / cleaned).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                findings.append(Finding(rel, f"relative Markdown link escapes repository root: {cleaned}", _line_for_offset(text, match.start())))
                continue
            if not candidate.exists():
                findings.append(Finding(rel, f"broken relative Markdown link: {cleaned}", _line_for_offset(text, match.start())))
    return findings


def _check_text_hygiene(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    private_key_markers = tuple(f"-----BEGIN {label}-----" for label in ("PRIVATE KEY", "RSA PRIVATE KEY", "EC PRIVATE KEY", "OPENSSH PRIVATE KEY"))
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
                findings.append(Finding(rel, "private-key material marker found in repository text", _line_for_offset(text, offset)))
    return findings


def validate_repository(root: Path) -> list[Finding]:
    root = root.resolve()
    findings = _check_workflow_policy(root) + _check_markdown_integrity(root) + _check_text_hygiene(root)
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
        print(f"::error file={_escape_annotation(finding.path)},line={finding.line}::{_escape_annotation(finding.message)}")
        print(f"- {finding.path}:{finding.line}: {finding.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
