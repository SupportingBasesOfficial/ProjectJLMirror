from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from worker import FixtureWhatsAppAdapter,NotificationDispatcher


class Port:
    def __init__(self): self.completed=[]
    def claim_dispatch(self,**kwargs):
        return {"state":"processing","notification_attempt_id":"attempt-a"}
    def complete_dispatch(self,**kwargs):
        self.completed.append(kwargs)
        return {"state":kwargs["attempt_state"],"duplicate":False}


class WorkerTests(unittest.TestCase):
    def test_sent_is_not_upgraded_to_delivered(self):
        port=Port()
        worker=NotificationDispatcher(port,FixtureWhatsAppAdapter("sent"),"worker-a")
        result=worker.dispatch(
            tenant_id="tenant-a",outbox_id="outbox-a",
            intent={"notification_intent_id":"intent-a","payload_hash":"hash-a"},
        )
        self.assertEqual(result["state"],"sent")
        self.assertEqual(port.completed[-1]["attempt_state"],"sent")

    def test_adapter_exception_becomes_unknown_not_failed(self):
        class Boom:
            version="fixture-whatsapp@1"
            def send(self,*,intent): raise RuntimeError("unknown outcome")
        port=Port()
        worker=NotificationDispatcher(port,Boom(),"worker-a")
        result=worker.dispatch(
            tenant_id="tenant-a",outbox_id="outbox-a",
            intent={"notification_intent_id":"intent-a","payload_hash":"hash-a"},
        )
        self.assertEqual(result["state"],"unknown")


if __name__=="__main__":
    unittest.main()
