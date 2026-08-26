#!/usr/bin/env python3
"""Observer-only validation for Wave 2 cell/async correctness substrate."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

AUTHORITY_BASE_SHA = "ff932cec10e3b7dcc13b050bb09d4a7efd634598"
AUTHORITY_BASE = f"main@{AUTHORITY_BASE_SHA}"
PROFILE = "jlmirror-wave2-correctness/v1"
EXPECTED_SLICES = ["impl.cell-data-runtime@1", "impl.async-core@1"]
EXPECTED_C2 = [
    "broker_or_job_transport",
    "serialization_and_schema_registry_product",
    "outbox_dispatch_claim_transport_adapter",
    "cache_coordination_or_replay_product",
    "message_equivalence_evidence_mechanism",
    "message_equivalence_kms_or_historical_verifier_backend",
    "database_ha_pooler_and_runtime_mapping",
    "reconciliation_operator_tooling",
]
EXPECTED_FORBIDDEN = [
    "broker_ack_for_consumer_effect_completion",
    "dispatcher_claim_for_exactly_once_delivery",
    "read_then_insert_for_inbox_admission",
    "message_id_without_trusted_identity_scope_for_duplicate_safety",
    "same_scoped_id_without_equivalence_proof_for_benign_duplicate",
    "missing_equivalence_evidence_for_duplicate_success",
    "payload_tenant_for_trusted_tenant_scope",
    "queue_or_topic_name_for_consumer_contract_identity",
    "queue_or_topic_cell_name_for_current_tenant_placement",
    "request_time_human_authorization_for_delayed_execution_authority",
    "broker_redelivery_for_external_effect_retry_authority",
    "timeout_for_external_effect_absence",
    "new_message_id_for_ambiguous_republication",
    "outbox_dispatch_state_for_domain_fact_authority",
    "mutable_delivery_metadata_for_immutable_message_meaning",
    "recovery_missing_state_for_never_happened",
    "stale_worker_generation_for_current_effect_authority",
    "product_or_incident_behavior_invented_by_wave2_substrate",
]
EXPECTED_MANIFEST = {
    "wave_id": "wave-2.cell-async-correctness@1",
    "authority_base": AUTHORITY_BASE,
    "implementation_slices": EXPECTED_SLICES,
    "scope": "transactional_and_async_correctness_substrate_only",
    "product_feature_activation": "none",
    "runtime_profiles": ["runtime.api@1", "runtime.worker@1"],
    "required_reliability_profiles": [
        "rel.cell-transactional-store@1",
        "rel.consumer-inbox-effect@1",
        "rel.replay-consume-state@1",
    ],
    "fixed_delivery_semantics": "at_least_once",
    "fixed_inbox_identity": "(consumer_contract,message_identity_scope,message_id)",
    "residual_c2_choices_not_selected": EXPECTED_C2,
    "forbidden_correctness_substitutions": EXPECTED_FORBIDDEN,
    "next_wave_authorized": False,
}
ALLOWED_DELTA_PREFIXES = (
    "implementation/wave-2/",
    "src/jlmirror_async/",
    "sql/wave2/",
    "tests/wave2/",
    "tools/async_core/",
)
ALLOWED_DELTA_EXACT = {".github/workflows/deterministic-assurance.yml"}


def _manifest_findings() -> list[str]:
    path = ROOT / "implementation/wave-2/IMPLEMENTATION_MANIFEST.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Wave 2 manifest unreadable: {exc}"]
    return [] if data == EXPECTED_MANIFEST else ["Wave 2 implementation manifest drift"]


def _state_findings() -> list[str]:
    text = (ROOT / "implementation/wave-2/STATE.md").read_text(encoding="utf-8")
    required = (
        f"Base: `main@{AUTHORITY_BASE_SHA}`",
        "Authorized scope: Wave 2 only",
        "Product activation: none",
        "Wave 3 authorization: not granted",
        "Merge authorization: not granted",
    )
    return [f"Wave 2 state missing boundary: {item}" for item in required if item not in text]


def _source_authority_findings() -> list[str]:
    owners = {
        "publication": ROOT / "docs/10-event-contracts/publication-outbox-and-producer-authority.md",
        "inbox": ROOT / "docs/10-event-contracts/consumer-inbox-idempotency-and-effects.md",
        "security": ROOT / "docs/10-event-contracts/security-tenant-context-and-data-classification.md",
        "sequencing": ROOT / "docs/16-implementation-readiness/11-initial-implementation-sequencing.md",
        "slices": ROOT / "docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md",
    }
    text = {name: path.read_text(encoding="utf-8") for name, path in owners.items()}
    requirements = (
        ("publication", "same transaction as the mutation"),
        ("publication", "retrying the same logical `message_id` is preferred"),
        ("inbox", "(consumer_contract, message_identity_scope, message_id)"),
        ("inbox", "A read-then-insert race is prohibited"),
        ("inbox", "reconciliation_required"),
        ("security", "resolves current placement"),
        ("security", "Human/session/membership authorization from message creation time does not persist automatically"),
        ("sequencing", "## Wave 2 — Transactional cell and async correctness substrate"),
        ("sequencing", "`impl.cell-data-runtime@1`"),
        ("sequencing", "`impl.async-core@1`"),
        ("slices", "`rel.consumer-inbox-effect@1`"),
        ("slices", "`rel.cell-transactional-store@1`"),
    )
    return [
        f"accepted Wave 2 authority anchor missing: {owner}:{anchor}"
        for owner, anchor in requirements
        if anchor not in text[owner]
    ]


def _stdlib_boundary_findings() -> list[str]:
    findings: list[str] = []
    stdlib = set(sys.stdlib_module_names)
    for path in sorted((SRC / "jlmirror_async").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in stdlib and name not in {"jlmirror_async", "jlmirror_authority"}:
                    findings.append(f"unaccepted third-party dependency in Wave 2 core: {path}:{name}")
    return findings


def _sql_findings() -> list[str]:
    path = ROOT / "sql/wave2/001_async_correctness.sql"
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    required = (
        "create table if not exists system.async_outbox_message",
        "unique (producer_message_scope, message_id)",
        "create table if not exists system.async_outbox_dispatch",
        "create table if not exists system.async_consumer_inbox",
        "primary key (consumer_contract, message_identity_scope, message_id)",
        "create table if not exists system.async_cross_authority_operation",
        "security invoker",
        "no grant statements are intentionally present",
    )
    findings = [f"Wave 2 SQL missing contract anchor: {item}" for item in required if item not in lowered]
    if " grant " in f" {lowered} " and "no grant statements" not in lowered:
        findings.append("Wave 2 SQL must not silently select serving/admin privilege mapping")
    if "security definer" in lowered:
        findings.append("Wave 2 SQL must not introduce SECURITY DEFINER authority")
    return findings


def _git_scope_findings() -> list[str]:
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{AUTHORITY_BASE_SHA}^{{commit}}"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        completed = subprocess.run(
            ["git", "diff", "--name-only", f"{AUTHORITY_BASE_SHA}...HEAD"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"Wave 2 scope proof unavailable: {exc}"]
    findings: list[str] = []
    for raw in completed.stdout.splitlines():
        path = raw.strip()
        if not path:
            continue
        if path in ALLOWED_DELTA_EXACT or any(path.startswith(prefix) for prefix in ALLOWED_DELTA_PREFIXES):
            continue
        findings.append(f"out-of-scope Wave 2 delta: {path}")
    return findings


def _workflow_findings() -> list[str]:
    text = (ROOT / ".github/workflows/deterministic-assurance.yml").read_text(encoding="utf-8")
    required = (
        "python3 -m unittest discover -s tests/wave2 -p 'test_*.py'",
        "python3 tools/async_core/validate_wave2.py",
        "persist-credentials: false",
        "permissions:\n  contents: read",
    )
    return [f"Wave 2 workflow wiring missing: {item}" for item in required if item not in text]


def validate() -> list[str]:
    findings: list[str] = []
    for check in (
        _manifest_findings,
        _state_findings,
        _source_authority_findings,
        _stdlib_boundary_findings,
        _sql_findings,
        _git_scope_findings,
        _workflow_findings,
    ):
        try:
            findings.extend(check())
        except Exception as exc:  # fail closed: validator defects are findings
            findings.append(f"{check.__name__} failed closed: {type(exc).__name__}: {exc}")
    return findings


def main() -> int:
    findings = validate()
    if findings:
        print(f"RESULT: FAIL — {PROFILE}")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"RESULT: PASS — {PROFILE} — Wave 2 correctness substrate conforms to deterministic guard set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
