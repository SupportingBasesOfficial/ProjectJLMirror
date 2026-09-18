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
        raise SystemExit("G8 runtime proof exposes self-check only")

    contract=json.loads((ROOT/"contracts/g8-human-operations/human-operations-v1.json").read_text(encoding="utf-8"))
    if contract["projection_only_action_kinds"]!=["no_human_action_required"]:
        raise SystemExit("G8 projection contract drift")
    if contract["visibility_capability_classes"]!=["platform_native_authenticated_view@1"]:
        raise SystemExit("G8 visibility contract drift")

    from domain import AuthoritySnapshot,require_action,require_visibility
    authority=AuthoritySnapshot("tenant-a","actor-a",True,"human-operations:write","r1")
    authority.validate(tenant_id="tenant-a",actor_principal_id="actor-a")
    require_action("investigate_alert")
    require_visibility("internal","platform_native_authenticated_view@1")
    print("g8_worker_boot=PASS authority=PASS action=PASS visibility=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
