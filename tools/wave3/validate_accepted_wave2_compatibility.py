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

# IMMUTABLE forever — anchors historical_scope_findings()'s proof of exactly what Wave 2's own
# acceptance PR (#24) contained. Must never move again; future_substrate_drift_findings() does
# NOT use this constant (see PROTECTED_WAVE2_DRIFT_BASELINE_SHA below for why).
ACCEPTED_WAVE2_SHA = "b1f5fb83d2aa53e981007dddd0b751e22db40eee"
PROFILE = "jlmirror-wave2-future-compatibility/v1"
PROTECTED_WAVE2_PREFIXES = (
    "implementation/wave-2/", "src/jlmirror_async/", "sql/wave2/",
    "tests/wave2/", "tools/async_core/",
)
PROTECTED_WAVE2_EXACT = frozenset({
    "tools/authority/wave1_scope.py", "tests/wave1/test_wave1_scope_guard.py",
})
# Deliberately SEPARATE from ACCEPTED_WAVE2_SHA. future_substrate_drift_findings() diffs against
# this pointer instead of the immutable historical anchor, because those are two different
# invariants that must not share one constant:
#   - ACCEPTED_WAVE2_SHA is a frozen, one-time fact ("what the original Wave 2 PR contained")
#     and can never move without falsifying that fact.
#   - This baseline is the live edge of "protected substrate has not silently drifted since it
#     was last explicitly, humanly reviewed" — and a genuine, authorized correction to protected
#     substrate (e.g. a bug in tools/async_core/'s own validator code) legitimately needs this
#     edge to advance, or the guard can never be corrected without permanently failing on itself.
#
# Repin convention for a future correction to protected substrate (no automated enforcement
# beyond this comment and ordinary PR review — this repo has no branch protection requiring
# green CI to merge, and already requires explicit human authorization for every single merge
# regardless of CI color):
#   1. The corrective PR lands with its fix. Its own resulting merge commit SHA cannot be known
#      in advance (GitHub computes it at merge time), so the PR is expected — and its description
#      should say so explicitly — to fail jlmirror-wave2-future-compatibility/v1 with exactly the
#      protected path(s) it touched, and nothing else.
#   2. An immediate, minimal follow-up PR bumps PROTECTED_WAVE2_DRIFT_BASELINE_SHA to the
#      corrective PR's actual merge SHA. That follow-up PR's own diff against the old baseline
#      (`git diff <old>..<new>`) is the entire review surface for what is being accepted, and
#      restores a green result.
# Precedent: incident of 2026-08-27 — PR #29's fix to tools/async_core/validate_wave2.py tripped
# this guard on the very next CI run because there was no legitimate way to repin. This mechanism
# closes that recursion while every one of the 5 protected prefixes above stays exactly as
# strictly frozen against live drift as before. PR that installs this mechanism also performs
# step 2 retroactively for #29 (already-known, historical merge SHA — zero red window).
PROTECTED_WAVE2_DRIFT_BASELINE_SHA = "8b7f1c34ea3ccbe8d98bb950c353fb4662f5085a"
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
        actual = _git_changed(PROTECTED_WAVE2_DRIFT_BASELINE_SHA, "HEAD") if paths is None else list(paths)
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
