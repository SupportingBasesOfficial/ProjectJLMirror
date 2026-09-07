#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from d4d_message_protection_source import run_probes
SOURCE=Path('implementation/d4-eventing-async/source-evidence/d4-d-message-protection-key-authority/source-evidence-manifest.json')

def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--repository-sha',required=True)
    p.add_argument('--workflow-run-id',required=True,type=int)
    p.add_argument('--workflow-run-attempt',required=True,type=int)
    p.add_argument('--job-id',required=True,type=int)
    p.add_argument('--job-name',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    proofs=run_probes()
    if not proofs or not all(proofs.values()):
        raise SystemExit('cannot emit provenance from failing proof set')
    out={
      'schema_version':1,
      'source_decision':'OPEN-EVT-017',
      'evidence_id':'message_protection_key_authority_and_historical_verifier_continuity',
      'message_protection_authority':'secret_or_kms_authority_with_historical_verifier_continuity',
      'repository_sha':a.repository_sha,
      'workflow_run_id':a.workflow_run_id,
      'workflow_run_attempt':a.workflow_run_attempt,
      'job_id':a.job_id,
      'job_name':a.job_name,
      'source_manifest_sha256':sha256(SOURCE),
      'proof_results':proofs,
      'selection':'not_selected',
      'selection_authority':'not_granted',
      'ledger_credit':[],
      'current_run_auto_credit':False
    }
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
