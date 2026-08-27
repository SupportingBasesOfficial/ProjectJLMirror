#!/usr/bin/env python3
"""Future-wave compatibility guard for the accepted Wave 2 substrate."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.async_core import validate_wave2 as wave2  # noqa: E402

ACCEPTED_WAVE2_SHA = "b1f5fb83d2aa53e981007dddd0b751e22db40eee"
PROFILE = "jlmirror-wave2-future-compatibility/v1"
PROTECTED_WAVE2_PREFIXES = (
    "implementation/wave-2/", "src/jlmirror_async/", "sql/wave2/",
    "tests/wave2/", "tools/async_core/",
)
PROTECTED_WAVE2_EXACT = frozenset({
    "tools/authority/wave1_scope.py", "tests/wave1/test_wave1_scope_guard.py",
})
# `implementation/wave-2/KNOWN_DEFERRED_ITEMS.md` is a living, forward-looking governance
# record (see its own header), not a frozen description of what Wave 2 built — unlike
# IMPLEMENTATION_MANIFEST.json/STATE.md/README.md/RECONCILIATION_AUTHORITY_BOUNDARY.md, which
# this guard must keep protecting exactly as before. It is expected to gain new entries or have
# existing ones marked closed as later waves resolve them, so it is named here explicitly rather
# than loosening the `implementation/wave-2/` prefix match for the rest of the protected substrate.
ALLOWED_GOVERNANCE_RECORD_PATHS = frozenset({
    "implementation/wave-2/KNOWN_DEFERRED_ITEMS.md",
})


def _canonical_repo_path(raw: str) -> str | None:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        return None
    pure = PurePosixPath(raw)
    if pure.is_absolute() or raw != str(pure) or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return raw


def _git_changed(base: str, head: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}..{head}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def historical_scope_findings(paths: list[str] | None = None) -> list[str]:
    try:
        actual = _git_changed(wave2.AUTHORITY_BASE_SHA, ACCEPTED_WAVE2_SHA) if paths is None else list(paths)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"accepted Wave 2 historical delta cannot be established: {exc}"]
    findings: list[str] = []
    for raw in actual:
        path = _canonical_repo_path(raw)
        if path is None:
            findings.append(f"accepted Wave 2 historical path is non-canonical: {raw!r}")
            continue
        if path in wave2.ALLOWED_DELTA_EXACT or path.startswith(wave2.ALLOWED_DELTA_PREFIXES):
            continue
        findings.append(f"accepted Wave 2 historical delta escapes authorized path set: {path}")
    return findings


def future_substrate_drift_findings(paths: list[str] | None = None) -> list[str]:
    try:
        actual = _git_changed(ACCEPTED_WAVE2_SHA, "HEAD") if paths is None else list(paths)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"future Wave 2 substrate drift proof unavailable: {exc}"]
    findings: list[str] = []
    for raw in actual:
        path = _canonical_repo_path(raw)
        if path is None:
            findings.append(f"future changed path is non-canonical: {raw!r}")
            continue
        if path in ALLOWED_GOVERNANCE_RECORD_PATHS:
            continue
        if path in PROTECTED_WAVE2_EXACT or path.startswith(PROTECTED_WAVE2_PREFIXES):
            findings.append(f"accepted Wave 2 protected substrate changed after acceptance: {path}")
    return findings


def workflow_findings() -> list[str]:
    text = (ROOT / ".github/workflows/deterministic-assurance.yml").read_text(encoding="utf-8")
    required = (
        "python3 -m unittest discover -s tests/wave2 -p 'test_*.py'",
        "python3 tools/wave3/validate_accepted_wave2_compatibility.py",
        "python3 tools/async_core/validate_reconciliation_attempt_binding.py",
        "python3 tools/async_core/validate_redrive_authority.py",
        "persist-credentials: false",
        "allow-unsafe-pr-checkout: false",
        "permissions:\n  contents: read",
    )
    return [f"future Wave 2 workflow wiring missing: {item}" for item in required if item not in text]


def semantic_findings() -> list[str]:
    findings: list[str] = []
    checks = (
        wave2._manifest_findings,
        wave2._state_findings,
        wave2._source_authority_findings,
        wave2._stdlib_boundary_findings,
        wave2._execution_boundary_findings,
        wave2._redrive_boundary_findings,
        wave2._reconciliation_authority_boundary_findings,
        wave2._sql_findings,
        wave2._wave1_compatibility_maintenance_findings,
    )
    for check in checks:
        try:
            findings.extend(check())
        except Exception as exc:
            findings.append(f"Wave 2 semantic compatibility check failed closed: {check.__name__}: {exc}")
    findings.extend(workflow_findings())
    return findings


def validate() -> list[str]:
    findings = semantic_findings()
    findings.extend(historical_scope_findings())
    findings.extend(future_substrate_drift_findings())
    return findings


def main() -> int:
    findings = validate()
    if findings:
        print(f"RESULT: FAIL — {PROFILE}")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"RESULT: PASS — {PROFILE}")
    print("accepted Wave 2 semantic checks, historical scope and future substrate immutability remain intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
