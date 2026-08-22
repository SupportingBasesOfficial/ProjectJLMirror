#!/usr/bin/env python3
"""Negative tests for JLMIRROR deterministic assurance v1."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import validate_repository as vr


PINNED = "3d3c42e5aac5ba805825da76410c181273ba90b1"


class AssuranceValidatorTests(unittest.TestCase):
    def make_repo(self, workflow: str = "", markdown: str = "# OK\n") -> tuple[TemporaryDirectory, Path]:
        temp = TemporaryDirectory()
        root = Path(temp.name)
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / "docs").mkdir()
        if workflow:
            (root / ".github" / "workflows" / "assurance.yml").write_text(workflow, encoding="utf-8")
        (root / "docs" / "index.md").write_text(markdown, encoding="utf-8")
        return temp, root

    def messages(self, root: Path) -> list[str]:
        return [finding.message for finding in vr.validate_repository(root)]

    def test_minimal_read_only_workflow_passes(self) -> None:
        workflow = f"""name: test
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@{PINNED}
        with:
          persist-credentials: false
      - run: python3 --version
"""
        temp, root = self.make_repo(workflow, "# OK\n\n[Self](index.md)\n")
        with temp:
            self.assertEqual(vr.validate_repository(root), [])

    def test_mutable_action_reference_is_rejected(self) -> None:
        workflow = """name: bad
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("immutable 40-hex" in message for message in self.messages(root)))

    def test_job_level_reusable_workflow_must_be_pinned(self) -> None:
        workflow = """name: bad
on: [push]
permissions:
  contents: read
jobs:
  call:
    uses: example/repo/.github/workflows/reusable.yml@main
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("immutable 40-hex" in message for message in self.messages(root)))

    def test_write_permission_is_rejected(self) -> None:
        workflow = """name: bad
on: [push]
permissions:
  contents: write
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - run: echo no
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("write permission" in message for message in self.messages(root)))

    def test_inline_write_permission_is_rejected(self) -> None:
        workflow = """name: bad
on: [push]
permissions: { contents: write }
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - run: echo no
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("inline write permission" in message for message in self.messages(root)))

    def test_pull_request_target_is_rejected(self) -> None:
        workflow = """name: bad
on:
  pull_request_target:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - run: echo no
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("pull_request_target" in message for message in self.messages(root)))

    def test_inline_pull_request_target_is_rejected(self) -> None:
        workflow = """name: bad
on: [push, pull_request_target]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - run: echo no
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("pull_request_target" in message for message in self.messages(root)))

    def test_checkout_credentials_must_not_persist(self) -> None:
        workflow = f"""name: bad
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@{PINNED}
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("persist-credentials" in message for message in self.messages(root)))

    def test_mutating_command_is_rejected(self) -> None:
        workflow = """name: bad
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - run: git push origin HEAD
"""
        temp, root = self.make_repo(workflow)
        with temp:
            self.assertTrue(any("git push" in message for message in self.messages(root)))

    def test_broken_relative_markdown_link_is_rejected(self) -> None:
        temp, root = self.make_repo(markdown="# Broken\n\n[Missing](missing.md)\n")
        with temp:
            self.assertTrue(any("broken relative Markdown link" in message for message in self.messages(root)))

    def test_private_key_marker_is_rejected(self) -> None:
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        temp, root = self.make_repo(markdown=f"# Secret\n\n{marker}\n")
        with temp:
            self.assertTrue(any("private-key material" in message for message in self.messages(root)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
