from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps/g3-resource-inventory"))


def load_bff():
    path = ROOT / "apps/g3-resource-inventory/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g3_cache_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G3 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G3 = load_bff()


class CacheContractTests(unittest.TestCase):
    def test_list_success_uses_private_revalidation_header(self):
        handler = object.__new__(G3.Handler)
        captured: list[tuple[str, str]] = []
        handler.wfile = BytesIO()
        handler.send_response = lambda status: captured.append(("status", str(status)))
        handler.send_header = lambda name, value: captured.append((name, value))
        handler.end_headers = lambda: None

        handler._send_private_json(200, {"items": [], "generation_state": "active_generation", "next_cursor": None})

        self.assertIn(("Cache-Control", "private, no-cache"), captured)
        self.assertNotIn(("Cache-Control", "no-store"), captured)


if __name__ == "__main__":
    unittest.main()
