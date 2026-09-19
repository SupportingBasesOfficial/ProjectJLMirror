from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-check",action="store_true")
    args=parser.parse_args()
    if not args.self_check:
        raise SystemExit("G9 runtime proof exposes self-check only")

    contract=json.loads((ROOT/"contracts/g9-notification-delivery/notification-delivery-v1.json").read_text(encoding="utf-8"))
    if contract["channel"]!="whatsapp_business@1":
        raise SystemExit("G9 channel drift")
    if contract["max_attempts"]!=3:
        raise SystemExit("G9 retry budget drift")
    if contract["external_read_is_authoritative_native_view"] is not False:
        raise SystemExit("G9 visibility authority drift")

    from domain import AuthoritySnapshot,require_intent
    authority=AuthoritySnapshot("tenant-a","actor-a",True,"notification:write","r1")
    authority.validate(tenant_id="tenant-a",actor_principal_id="actor-a")
    require_intent("alert_requires_attention","whatsapp_business@1")
    print("g9_worker_boot=PASS authority=PASS channel=PASS visibility_separation=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
