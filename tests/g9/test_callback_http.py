from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
import hmac
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from callback import Route,WhatsAppCallbackBoundary
from callback_http import make_callback_handler


class Port:
    def __init__(self): self.calls=[]
    def record_provider_callback(self,**kwargs):
        self.calls.append(kwargs)
        return {"callback_inbox_id":"cb-a","state":"processed","duplicate":False}


class CallbackHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port=Port()
        cls.secret=b"http-callback-secret"
        boundary=WhatsAppCallbackBoundary(
            cls.port,{"account-a":Route("account-a","tenant-a",cls.secret)}
        )
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),make_callback_handler(boundary))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self,body:bytes,*,signature:str,timestamp:int,account:str="account-a"):
        req=Request(
            self.base+"/api/v1/provider-callbacks/whatsapp",
            data=body,method="POST",
            headers={
                "Content-Type":"application/json",
                "X-Provider-Account-Ref":account,
                "X-Provider-Callback-Ref":"callback-a",
                "X-Provider-Message-Ref":"message-a",
                "X-Provider-Evidence-Kind":"delivered",
                "X-Provider-Timestamp":str(timestamp),
                "X-Provider-Signature":signature,
            },
        )
        with urlopen(req,timeout=2) as response:
            return response.status,json.loads(response.read())

    def test_http_callback_verifies_and_minimizes(self):
        body=json.dumps({
            "status":"delivered",
            "message_text":"sensitive-content-must-not-persist",
            "tenant_id":"attacker-tenant",
        },separators=(",",":")).encode()
        ts=int(datetime.now(timezone.utc).timestamp())
        sig=hmac.new(self.secret,str(ts).encode()+b"."+body,sha256).hexdigest()
        status,value=self.request(body,signature=sig,timestamp=ts)
        self.assertEqual(status,200)
        self.assertEqual(value["state"],"processed")
        call=self.port.calls[-1]
        self.assertEqual(call["tenant_id"],"tenant-a")
        self.assertEqual(call["bounded_payload"],{"status":"delivered"})

    def test_invalid_signature_is_unauthorized(self):
        body=b'{"status":"delivered"}'
        ts=int(datetime.now(timezone.utc).timestamp())
        with self.assertRaises(HTTPError) as caught:
            self.request(body,signature="00",timestamp=ts)
        self.assertEqual(caught.exception.code,401)


if __name__=="__main__":
    unittest.main()
