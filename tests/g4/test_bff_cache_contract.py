from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps/g4-metrics"))


def load_bff():
    path = ROOT / "apps/g4-metrics/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g4_cache_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G4 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G4 = load_bff()


class CacheTests(unittest.TestCase):
    def test_definition_list_private_revalidate_profile(self):
        handler = object.__new__(G4.Handler)
        captured = []
        handler.wfile = BytesIO()
        handler.send_response = lambda status: captured.append(("status", str(status)))
        handler.send_header = lambda name, value: captured.append((name, value))
        handler.end_headers = lambda: None
        handler._send_private_json(200, {"items": [], "next_cursor": None})
        self.assertIn(("Cache-Control", "private, no-cache"), captured)

    def test_inherited_json_is_no_store_for_current_and_history(self):
        # Canonical G1/G3 protected JSON writer is the no-store surface inherited by G4.
        source = (ROOT / "apps/g1-identity-tenant-shell/bff_server.py").read_text(encoding="utf-8")
        self.assertIn('self.send_header("Cache-Control", "no-store")', source)


if __name__ == "__main__":
    unittest.main()
