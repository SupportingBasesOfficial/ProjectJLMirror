from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.contracts.core import ContractProjectionError, validate_authority_base_bindings


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout.strip()


def _registry(base: str, blob: str) -> dict:
    manifest = {
        "path": "docs/manifest.md",
        "git_blob_sha": blob,
        "heading": "Semantic manifest",
        "composite_requirements": [],
    }
    return {
        "accepted_authority_base": base,
        "profile_sources": [{"path": "docs/manifest.md", "git_blob_sha": blob}],
        "http_manifest_source": dict(manifest),
        "event_manifest_source": dict(manifest),
    }


class SquashSafeAuthorityBindingTests(unittest.TestCase):
    def test_durable_base_can_precede_evaluated_head_source_update(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "docs" / "manifest.md"
            source.parent.mkdir(parents=True)
            source.write_text("# A\n\n## Semantic manifest\n```text\ncontract_name\n```\n`runtime.api@1`\n", encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "test@example.invalid")
            _git(root, "config", "user.name", "JLMIRROR Test")
            _git(root, "add", "docs/manifest.md")
            _git(root, "commit", "-q", "-m", "accepted base")
            base = _git(root, "rev-parse", "HEAD")

            source.write_text("# A\n\n## Semantic manifest\n```text\ncontract_name\n```\n`runtime.worker@1`\n", encoding="utf-8")
            _git(root, "add", "docs/manifest.md")
            _git(root, "commit", "-q", "-m", "candidate source handoff")
            evaluated = _git(root, "rev-parse", "HEAD")
            blob = _git(root, "rev-parse", f"{evaluated}:docs/manifest.md")

            validate_authority_base_bindings(root, _registry(base, blob))

    def test_unrelated_base_is_rejected_even_when_head_blob_matches(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "docs" / "manifest.md"
            source.parent.mkdir(parents=True)
            source.write_text("# A\n\n## Semantic manifest\n```text\ncontract_name\n```\n`runtime.api@1`\n", encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "test@example.invalid")
            _git(root, "config", "user.name", "JLMIRROR Test")
            _git(root, "add", "docs/manifest.md")
            _git(root, "commit", "-q", "-m", "candidate")
            candidate = _git(root, "rev-parse", "HEAD")
            blob = _git(root, "rev-parse", f"{candidate}:docs/manifest.md")

            _git(root, "checkout", "--orphan", "unrelated")
            _git(root, "rm", "-q", "-rf", ".")
            other = root / "docs" / "other.md"
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_text("unrelated\n", encoding="utf-8")
            _git(root, "add", "docs/other.md")
            _git(root, "commit", "-q", "-m", "unrelated base")
            unrelated = _git(root, "rev-parse", "HEAD")
            _git(root, "checkout", "-q", candidate)

            with self.assertRaisesRegex(
                ContractProjectionError,
                "accepted_authority_base is not an ancestor",
            ):
                validate_authority_base_bindings(root, _registry(unrelated, blob))


if __name__ == "__main__":
    unittest.main()
