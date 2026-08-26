#!/usr/bin/env python3
"""Historical exact-delta scope guard for the accepted Wave 1 implementation.

The default proof is intentionally pinned to the accepted Wave 1 squash commit.
Future authorized waves may add their own paths without retroactively becoming
part of Wave 1. Synthetic `paths=` validation still evaluates the original Wave 1
allow-list and therefore remains useful for falsifying scope expansion.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

AUTHORITY_BASE_SHA = "5b56ad94566b48b72a993ee8f5cf7e983127ab21"
ACCEPTED_WAVE1_SHA = "ff932cec10e3b7dcc13b050bb09d4a7efd634598"
ALLOWED_EXACT_PATHS = frozenset({".github/workflows/deterministic-assurance.yml"})
ALLOWED_PREFIXES = (
    "implementation/wave-1/",
    "sql/wave1/",
    "src/jlmirror_authority/",
    "tests/wave1/",
    "tools/authority/",
)


def _canonical_repo_path(value: str) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    canonical = path.as_posix()
    return canonical if canonical == value else None


def changed_paths(root: Path, *, head: str = ACCEPTED_WAVE1_SHA) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{AUTHORITY_BASE_SHA}..{head}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def validate_wave1_scope(
    root: Path,
    *,
    paths: list[str] | None = None,
    head: str = ACCEPTED_WAVE1_SHA,
) -> list[str]:
    try:
        actual = changed_paths(root, head=head) if paths is None else list(paths)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"Wave 1 accepted exact-base Git delta cannot be established: {exc}"]

    findings: list[str] = []
    seen: set[str] = set()
    for raw in actual:
        path = _canonical_repo_path(raw)
        if path is None:
            findings.append(f"Wave 1 changed path is non-canonical: {raw!r}")
            continue
        if path in seen:
            findings.append(f"Wave 1 changed path is duplicated: {path}")
            continue
        seen.add(path)
        if path in ALLOWED_EXACT_PATHS or path.startswith(ALLOWED_PREFIXES):
            continue
        findings.append(f"Wave 1 delta escapes authorized path set: {path}")
    return findings
