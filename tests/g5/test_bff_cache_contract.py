from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g5-problem-health"))


def load_bff():
    path=ROOT/"apps/g5-problem-health/bff_server.py"
    spec=importlib.util.spec_from_file_location("jlmirror_g5_cache_test",path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G5 BFF cannot be loaded")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


G5=load_bff()


class CacheTests(unittest.TestCase):
    def test_health_success_uses_private_revalidation(self):
        handler=object.__new__(G5.Handler)
        captured=[]
        handler.wfile=BytesIO()
        handler.send_response=lambda status: captured.append(("status",str(status)))
        handler.send_header=lambda name,value: captured.append((name,value))
        handler.end_headers=lambda: None
        handler._send_private_json(200,{"items":[],"next_cursor":None})
        self.assertIn(("Cache-Control","private, no-cache"),captured)

    def test_problem_json_writer_is_no_store(self):
        source=(ROOT/"apps/g1-identity-tenant-shell/bff_server.py").read_text(encoding="utf-8")
        self.assertIn('self.send_header("Cache-Control", "no-store")',source)


if __name__=="__main__":
    unittest.main()
