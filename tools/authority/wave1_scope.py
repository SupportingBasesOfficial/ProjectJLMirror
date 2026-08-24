#!/usr/bin/env python3
"""Exact-base Git delta scope guard for the authorized Wave 1 implementation."""

from __future__ import annotations

from pathlib import Path
import subprocess

AUTHORITY_BASE_SHA = "5b56ad94566b48b72a993ee8f5cf7e983127ab21"
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


def changed_paths(root: Path, *, head: str = "HEAD") -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{AUTHORITY_BASE_SHA}..{head}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def validate_wave1_scope(root: Path, *, paths: list[str] | None = None) -> list[str]:
    try:
        actual = changed_paths(root) if paths is None else list(paths)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"Wave 1 exact-base Git delta cannot be established: {exc}"]

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
