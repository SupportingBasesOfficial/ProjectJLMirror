from __future__ import annotations
import argparse,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--self-check",action="store_true");a=p.parse_args()
    if not a.self_check: raise SystemExit("G10 runtime proof exposes self-check only")
    c=json.loads((ROOT/"contracts/g10-itsm/incident-v1.json").read_text())
    if c["object_type"]!="incident": raise SystemExit("object drift")
    if c["provider_adapter_contract"]!="itsm_provider_neutral@1": raise SystemExit("adapter drift")
    if "resolved->open" in c["allowed_transitions"]: raise SystemExit("reopen drift")
    from domain import AuthoritySnapshot,require_transition
    s=AuthoritySnapshot("tenant-a","actor-a",True,"itsm:write","r1")
    s.validate(tenant_id="tenant-a",actor_principal_id="actor-a")
    require_transition("open","resolved")
    print("g10_worker_boot=PASS authority=PASS incident=PASS provider_neutral=PASS")
    return 0

if __name__=="__main__":raise SystemExit(main())
