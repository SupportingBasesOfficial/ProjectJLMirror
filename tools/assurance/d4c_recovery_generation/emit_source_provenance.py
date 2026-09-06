#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
SOURCE = Path('implementation/d4-eventing-async/source-evidence/d4-c-recovery-generation-source.json')
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--repository-sha',required=True); p.add_argument('--workflow-run-id',required=True,type=int)
    p.add_argument('--workflow-run-attempt',required=True,type=int); p.add_argument('--job-id',required=True,type=int)
    p.add_argument('--job-name',required=True); p.add_argument('--candidate-results',required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); results=Path(a.candidate_results); data=json.loads(results.read_text(encoding='utf-8'))
    out={
        'schema_version':1,'source_decision':'OPEN-EVT-025','evidence_id':'recovery_generation_rf_inventory_reconciliation_and_activation_gates',
        'repository_sha':a.repository_sha,'workflow_run_id':a.workflow_run_id,'workflow_run_attempt':a.workflow_run_attempt,
        'job_id':a.job_id,'job_name':a.job_name,'source_manifest_sha256':sha256(SOURCE),'candidate_results_sha256':sha256(results),
        'candidate_results':data['candidate_results'],'proof_results':data['proof_results'],'selection':'not_selected',
        'selection_authority':'not_granted','ledger_credit':[],'current_run_auto_credit':False,
    }
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8'); return 0
if __name__ == '__main__': raise SystemExit(main())
