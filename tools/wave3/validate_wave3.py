from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "implementation/wave-3/IMPLEMENTATION_MANIFEST.json"
REGISTRY = ROOT / "implementation/wave-3/source-registry.json"

REQUIRED_FILES = (
    "src/jlmirror_observability/__init__.py",
    "src/jlmirror_observability/model.py",
    "src/jlmirror_observability/policy.py",
    "src/jlmirror_release/__init__.py",
    "src/jlmirror_release/model.py",
    "src/jlmirror_release/authority.py",
    "src/jlmirror_release/configuration.py",
    "src/jlmirror_release/verification.py",
    "tests/wave3/test_observability.py",
    "tests/wave3/test_release.py",
    "implementation/wave-3/README.md",
    "implementation/wave-3/IMPLEMENTATION_MANIFEST.json",
    "implementation/wave-3/source-registry.json",
)

EXPECTED_SLICES = ["impl.observability@1", "impl.release-supply-chain@1"]
EXPECTED_BASE = "b1f5fb83d2aa53e981007dddd0b751e22db40eee"


def fail(message: str) -> None:
    raise SystemExit(f"WAVE3 VALIDATION FAILED: {message}")


def git_blob_at(commit: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"cannot resolve accepted authority source {commit}:{path}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def validate() -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            fail(f"required Wave 3 file missing: {relative}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("authority_base") != f"main@{EXPECTED_BASE}":
        fail("implementation manifest authority_base drift")
    if manifest.get("implementation_slices") != EXPECTED_SLICES:
        fail("implementation slice set/order drift")
    if manifest.get("product_feature_activation") != "none":
        fail("Wave 3 cannot activate Product features")
    if manifest.get("next_wave_authorized") is not False:
        fail("Wave 4 cannot be authorized by Wave 3 implementation metadata")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry.get("accepted_authority_base") != EXPECTED_BASE:
        fail("source registry accepted_authority_base drift")
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        fail("source registry must contain pinned sources")
    seen: set[str] = set()
    for source in sources:
        path = source.get("path")
        sha = source.get("git_blob_sha")
        if not isinstance(path, str) or not path.startswith("docs/") or ".." in Path(path).parts:
            fail(f"non-canonical source path: {path!r}")
        if path in seen:
            fail(f"duplicate source path: {path}")
        seen.add(path)
        if not isinstance(sha, str) or len(sha) != 40:
            fail(f"invalid source blob sha for {path}")
        actual = git_blob_at(EXPECTED_BASE, path)
        if actual != sha:
            fail(f"accepted-base binding mismatch for {path}: expected {sha}, got {actual}")

    workflow = (ROOT / ".github/workflows/deterministic-assurance.yml").read_text(encoding="utf-8")
    if "tests/wave3" not in workflow or "tools/wave3/validate_wave3.py" not in workflow:
        fail("deterministic assurance workflow does not execute Wave 3 tests and validator")

    print("WAVE3 VALIDATION: PASS — observability/release substrate remains pinned and non-Product.")


if __name__ == "__main__":
    validate()
