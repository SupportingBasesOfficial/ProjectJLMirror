from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
import hmac
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from callback import Route,WhatsAppCallbackBoundary


class Port:
    def __init__(self): self.calls=[]
    def record_provider_callback(self,**kwargs):
        self.calls.append(kwargs)
        return {"duplicate":False,"state":"processed"}


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.port=Port()
        self.secret=b"callback-test-secret"
        self.boundary=WhatsAppCallbackBoundary(
            self.port,
            {"account-a":Route("account-a","tenant-a",self.secret)},
        )

    def sign(self,ts:int,body:bytes)->str:
        return hmac.new(self.secret,str(ts).encode()+b"."+body,sha256).hexdigest()

    def test_verified_callback_uses_trusted_route_tenant(self):
        body=json.dumps({"status":"delivered","tenant_id":"attacker-tenant"},separators=(",",":")).encode()
        ts=int(datetime.now(timezone.utc).timestamp())
        result=self.boundary.admit(
            provider_account_ref="account-a",callback_ref="cb-1",
            provider_message_ref="provider-msg-1",evidence_kind="delivered",
            body=body,timestamp_epoch=ts,signature_hex=self.sign(ts,body),
        )
        self.assertEqual(result["state"],"processed")
        self.assertEqual(self.port.calls[-1]["tenant_id"],"tenant-a")
        self.assertTrue(self.port.calls[-1]["authentication_evidence"]["verified"])

    def test_invalid_signature_and_replay_window_fail_closed(self):
        body=b'{"status":"delivered"}'
        ts=int(datetime.now(timezone.utc).timestamp())
        with self.assertRaises(PermissionError):
            self.boundary.admit(
                provider_account_ref="account-a",callback_ref="cb-2",
                provider_message_ref="provider-msg-1",evidence_kind="delivered",
                body=body,timestamp_epoch=ts,signature_hex="00",
            )
        old=ts-301
        with self.assertRaises(PermissionError):
            self.boundary.admit(
                provider_account_ref="account-a",callback_ref="cb-3",
                provider_message_ref="provider-msg-1",evidence_kind="delivered",
                body=body,timestamp_epoch=old,signature_hex=self.sign(old,body),
            )


if __name__=="__main__":
    unittest.main()
