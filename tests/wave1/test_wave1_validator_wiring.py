from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority import validate_wave1  # noqa: E402


class Wave1ValidatorWiringTests(unittest.TestCase):
    def test_real_fence_migrations_are_required_by_central_validator(self):
        self.assertEqual(validate_wave1._fence_sql_findings(), [])

    def test_missing_revalidation_migration_is_a_central_gate_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            target = fake_root / "sql" / "wave1"
            target.mkdir(parents=True)
            shutil.copy2(
                ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql",
                target / "001_platform_authority_fence.sql",
            )
            with patch.object(validate_wave1, "ROOT", fake_root):
                findings = validate_wave1._fence_sql_findings()
        self.assertTrue(
            any("persisted fence revalidation migration unreadable" in f for f in findings)
        )

    def test_weakened_revalidation_migration_is_a_central_gate_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            target = fake_root / "sql" / "wave1"
            target.mkdir(parents=True)
            shutil.copy2(
                ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql",
                target / "001_platform_authority_fence.sql",
            )
            text = (
                ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"
            ).read_text(encoding="utf-8")
            text = text.replace(
                "ALTER TABLE platform.authority_fences\n    VALIDATE CONSTRAINT wave1_fence_epoch_positive;\n",
                "",
                1,
            )
            (target / "002_revalidate_authority_fence_contract.sql").write_text(
                text, encoding="utf-8"
            )
            with patch.object(validate_wave1, "ROOT", fake_root):
                findings = validate_wave1._fence_sql_findings()
        self.assertTrue(any("wave1_fence_epoch_positive" in f for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
