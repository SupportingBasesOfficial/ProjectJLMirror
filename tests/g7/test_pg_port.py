from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g7-alert-policy-lifecycle"))

from pg_port import PgAlertPolicyLifecycleGateway


class Cursor:
    def __init__(self, owner):
        self.owner=owner
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self, statement, params):
        self.owner.calls.append((statement,params))
    def fetchone(self):
        return (self.owner.result,)


class Connection:
    def __init__(self, result):
        self.result=result
        self.calls=[]
    def cursor(self): return Cursor(self)


class PgPortTests(unittest.TestCase):
    def test_gateway_calls_guarded_functions_only(self):
        conn=Connection({"effect":"create","alert_id":"a"})
        gateway=PgAlertPolicyLifecycleGateway(conn)
        result=gateway.evaluate_current("tenant-a","policy-a",1,"problem-1")
        self.assertEqual(result["effect"],"create")
        statement,_=conn.calls[-1]
        self.assertEqual(statement,"SELECT alerting.g7_apply_current_evaluation(%s,%s,%s,%s)")

    def test_read_gateway_is_bounded_function_surface(self):
        conn=Connection([])
        gateway=PgAlertPolicyLifecycleGateway(conn)
        self.assertEqual(gateway.list_alerts("tenant-a",50),[])
        self.assertEqual(conn.calls[-1][0],"SELECT alerting.g7_list_alerts(%s,%s)")


if __name__=="__main__":
    unittest.main()
