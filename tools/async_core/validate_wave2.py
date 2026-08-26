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
    "same_canonical_inbox_key_with_conflicting_trusted_tenant_binding_for_benign_duplicate",
    "missing_equivalence_evidence_for_duplicate_success",
    "payload_tenant_for_trusted_tenant_scope",
    "queue_or_topic_name_for_consumer_contract_identity",
    "queue_or_topic_cell_name_for_current_tenant_placement",
    "request_time_human_authorization_for_delayed_execution_authority",
    "stale_or_missing_current_execution_admission_for_effect_authority",
    "lease_expiry_for_effect_absence",
    "expired_inbox_or_external_effect_claim_for_automatic_retry_eligibility",
    "reconciliation_state_without_durable_resolution_revision_for_retry_or_completion",
    "caller_supplied_result_link_for_reconciliation_completion_without_operation_evidence",
    "operation_bound_receipt_completed_through_local_effect_path",
    "reconciliation_revision_reuse_for_different_evidence",
    "preseeded_reconciliation_revision_before_ambiguity",
    "mutable_or_deletable_reconciliation_evidence",
    "direct_state_update_for_reconciliation_bypass",
    "mutable_inbox_identity_tenant_or_comparison_evidence",
    "mutable_cross_authority_operation_identity_or_owner_scope",
    "same_state_claim_owner_generation_or_admission_rewrite",
    "broker_redelivery_for_external_effect_retry_authority",
    "timeout_for_external_effect_absence",
    "new_message_id_for_ambiguous_republication",
    "outbox_dispatch_state_for_domain_fact_authority",
    "mutable_delivery_metadata_for_immutable_message_meaning",
    "dispatch_time_for_authoritative_event_occurrence",
    "job_command_without_durable_operation_identity",
    "preexisting_same_name_correctness_table_for_schema_conformance",
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
    "fixed_execution_admission": "revision_bound_current_authority_before_each_protected_effect_attempt",
    "fixed_lease_loss_semantics": "lease_expiry_never_proves_effect_absence",
    "fixed_cross_authority_direct_completion_authority": "operation_bound_receipt_requires_exact_direct_completed_operation_outcome",
    "fixed_reconciliation_evidence": "append_only_operation_scoped_revision_plus_canonical_resolution_required_for_retry_or_confirmed_completion",
    "fixed_reconciliation_completion_authority": "stable_operation_plus_append_only_effect_confirmed_revision_required_after_reconciliation_block",
    "durable_schema_reuse_policy": "preexisting_wave2_correctness_object_requires_reviewed_revalidation_not_if_not_exists_acceptance",
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
ALLOWED_DELTA_EXACT = {
    ".github/workflows/deterministic-assurance.yml",
    "tools/authority/wave1_scope.py",
    "tests/wave1/test_wave1_scope_guard.py",
}
CRITICAL_TABLES = (
    "system.async_outbox_message",
    "system.async_outbox_dispatch",
    "system.async_consumer_inbox",
    "system.async_cross_authority_operation",
    "system.async_cross_authority_reconciliation",
)


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
        "envelope": ROOT / "docs/10-event-contracts/message-envelope-and-classes.md",
        "publication": ROOT / "docs/10-event-contracts/publication-outbox-and-producer-authority.md",
        "delivery": ROOT / "docs/10-event-contracts/delivery-ack-retry-and-quarantine.md",
        "inbox": ROOT / "docs/10-event-contracts/consumer-inbox-idempotency-and-effects.md",
        "security": ROOT / "docs/10-event-contracts/security-tenant-context-and-data-classification.md",
        "reliability": ROOT / "docs/11-reliability-resilience/08-reliability-semantic-manifest.md",
        "sequencing": ROOT / "docs/16-implementation-readiness/11-initial-implementation-sequencing.md",
        "slices": ROOT / "docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md",
    }
    text = {name: path.read_text(encoding="utf-8") for name, path in owners.items()}
    requirements = (
        ("envelope", "Events use `occurred_at`"),
        ("envelope", "Jobs use `created_at`"),
        ("envelope", "operation_id"),
        ("publication", "same transaction as the mutation"),
        ("publication", "claim/lease/locking semantics"),
        ("publication", "retrying the same logical `message_id` is preferred"),
        ("delivery", "worker lease expiry is not effect absence proof"),
        ("delivery", "lease timeout while original executor may still be active"),
        ("inbox", "(consumer_contract, message_identity_scope, message_id)"),
        ("inbox", "A read-then-insert race is prohibited"),
        ("inbox", "reconciliation_required"),
        ("inbox", "reconciliation decides whether another attempt is eligible"),
        ("security", "resolves current placement"),
        ("security", "Human/session/membership authorization from message creation time does not persist automatically"),
        ("reliability", "`rel.consumer-inbox-effect@1`"),
        ("reliability", "`rel.replay-consume-state@1`"),
        ("sequencing", "## Wave 2 — Transactional cell and async correctness substrate"),
        ("sequencing", "`impl.cell-data-runtime@1`"),
        ("sequencing", "`impl.async-core@1`"),
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


def _execution_boundary_findings() -> list[str]:
    execution = (ROOT / "src/jlmirror_async/execution.py").read_text(encoding="utf-8")
    inbox = (ROOT / "src/jlmirror_async/inbox.py").read_text(encoding="utf-8")
    reconciliation = (ROOT / "src/jlmirror_async/reconciliation.py").read_text(encoding="utf-8")
    required = (
        (execution, "class CurrentAsyncExecutionAuthorityPort"),
        (execution, "def require_current_execution("),
        (execution, "runtime.api@1"),
        (execution, "runtime.worker@1"),
        (inbox, "require_current_execution(execution_authority, request)"),
        (inbox, "processing_lease_expired_effect_absence_unproven"),
        (inbox, "same_scoped_identity_conflicting_trusted_binding"),
        (inbox, "operation-bound receipt requires cross-authority outcome authority"),
        (inbox, "def complete_cross_authority_effect("),
        (inbox, "bound operation has not durably completed with exact outcome"),
        (inbox, "reconciled operation completion must use reconciliation completion path"),
        (inbox, "def reconcile_retry_eligible("),
        (inbox, "ReconciliationResolution.EFFECT_PROVEN_ABSENT"),
        (inbox, "reconciliation completion requires stable operation identity and durable evidence authority"),
        (inbox, "ReconciliationResolution.EFFECT_CONFIRMED"),
        (reconciliation, "class ReconciliationEvidence"),
        (reconciliation, "self._reconciliation_evidence"),
        (reconciliation, "reconciliation revision cannot be reused for different evidence"),
        (reconciliation, "require_current_execution(execution_authority, request)"),
        (reconciliation, "attempt_lease_expired_effect_absence_unproven"),
    )
    return [
        f"Wave 2 current/reconciliation boundary missing: {anchor}"
        for text, anchor in required
        if anchor not in text
    ]


def _reconciliation_authority_boundary_findings() -> list[str]:
    boundary = (
        ROOT / "implementation/wave-2/RECONCILIATION_AUTHORITY_BOUNDARY.md"
    ).read_text(encoding="utf-8")
    test = (
        ROOT / "tests/wave2/test_reconciliation_completion_authority.py"
    ).read_text(encoding="utf-8")
    required_boundary = (
        "CALLER-SUPPLIED RESULT LINK != EFFECT COMPLETION AUTHORITY",
        "OPERATION-BOUND RECEIPT != LOCAL EFFECT PATH",
        "OPERATION-BOUND PROCESSING -> LOCAL COMPLETION = PROHIBITED",
        "RECONCILED OPERATION -> DIRECT PROCESSING COMPLETION = PROHIBITED",
        "append-only reconciliation evidence records `effect_confirmed`",
        "exactly matches the result linked by the inbox receipt",
    )
    required_tests = (
        "test_operation_bound_receipt_cannot_use_local_completion",
        "test_direct_cross_authority_completion_requires_exact_durable_outcome",
        "test_direct_cross_authority_completion_rejects_mismatched_outcome",
        "test_reconciled_operation_cannot_use_direct_processing_completion_path",
        "test_caller_result_link_cannot_complete_unbound_reconciliation",
        "test_bound_operation_without_operation_authority_remains_blocked",
        "test_append_only_confirmed_operation_evidence_allows_exact_completion",
        "test_confirmed_operation_with_mismatched_result_remains_blocked",
    )
    findings = [
        f"Wave 2 reconciliation authority boundary missing: {anchor}"
        for anchor in required_boundary
        if anchor not in boundary
    ]
    findings.extend(
        f"Wave 2 reconciliation authority falsification missing: {anchor}"
        for anchor in required_tests
        if anchor not in test
    )
    return findings


def _sql_findings() -> list[str]:
    initial = (ROOT / "sql/wave2/001_async_correctness.sql").read_text(encoding="utf-8")
    reconciliation = (
        ROOT / "sql/wave2/002_reconciliation_evidence_and_transition_hardening.sql"
    ).read_text(encoding="utf-8")
    completion = (
        ROOT / "sql/wave2/003_cross_authority_completion_hardening.sql"
    ).read_text(encoding="utf-8")
    text = initial + "\n" + reconciliation + "\n" + completion
    lowered = text.lower()
    required = (
        "create table system.async_outbox_message",
        "unique (producer_message_scope, message_id)",
        "create table system.async_outbox_dispatch",
        "claim_expires_at timestamptz null",
        "create function system.wave2_initialize_outbox_dispatch()",
        "after insert on system.async_outbox_message",
        "insert into system.async_outbox_dispatch(outbox_record_id)",
        "create table system.async_consumer_inbox",
        "primary key (consumer_contract, message_identity_scope, message_id)",
        "create table system.async_cross_authority_operation",
        "create table system.async_cross_authority_reconciliation",
        "primary key (operation_id, reconciliation_revision)",
        "before insert on system.async_cross_authority_reconciliation",
        "before update or delete on system.async_cross_authority_reconciliation",
        "wave2_operation_reconciliation_revision_fk",
        "wave2_inbox_reconciliation_revision_fk",
        "create or replace function system.wave2_guard_outbox_dispatch_update()",
        "create or replace function system.wave2_guard_cross_authority_operation_update()",
        "create or replace function system.wave2_guard_consumer_inbox_update()",
        "attempt_expires_at timestamptz null",
        "reconciliation_revision text null",
        "effect_proven_absent",
        "effect_confirmed",
        "wave 2 reconciliation exit requires bound operation + evidence revision",
        "operation-bound wave 2 inbox completion requires exact direct durable operation outcome",
        "execution_admission_revision text null",
        "execution_authorization_revision text null",
        "execution_principal_credential_generation text null",
        "execution_runtime_profile_id text null",
        "execution_runtime_generation text null",
        "execution_environment_class text null",
        "execution_placement_version text null",
        "execution_fence_scope_id text null",
        "execution_fence_epoch bigint null",
        "security invoker",
        "no grant statements are intentionally present",
    )
    findings = [f"Wave 2 SQL missing contract anchor: {item}" for item in required if item not in lowered]
    for table in CRITICAL_TABLES:
        if f"create table if not exists {table}" in lowered:
            findings.append(f"Wave 2 SQL silently reuses critical correctness table: {table}")
    if "currently reconciliation-blocked operation" not in lowered:
        findings.append("reconciliation evidence pre-seeding guard is missing")
    if "append-only" not in lowered:
        findings.append("reconciliation evidence immutability guard is missing")
    if "same-state wave 2 operation cannot rewrite claim/outcome/reconciliation evidence" not in lowered:
        findings.append("same-state operation rewrite guard is missing")
    if "same-state wave 2 inbox cannot rewrite claim/result/reconciliation evidence" not in lowered:
        findings.append("same-state inbox rewrite guard is missing")
    executable_grants = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("--") and line.strip().upper().startswith("GRANT ")
    ]
    if executable_grants:
        findings.append("Wave 2 SQL must not silently select serving/admin privilege mapping")
    if "security definer" in lowered:
        findings.append("Wave 2 SQL must not introduce SECURITY DEFINER authority")
    return findings


def _wave1_compatibility_maintenance_findings() -> list[str]:
    scope_text = (ROOT / "tools/authority/wave1_scope.py").read_text(encoding="utf-8")
    test_text = (ROOT / "tests/wave1/test_wave1_scope_guard.py").read_text(encoding="utf-8")
    required_scope = (
        'AUTHORITY_BASE_SHA = "5b56ad94566b48b72a993ee8f5cf7e983127ab21"',
        f'ACCEPTED_WAVE1_SHA = "{AUTHORITY_BASE_SHA}"',
        'head: str = ACCEPTED_WAVE1_SHA',
        '"implementation/wave-1/"',
        '"src/jlmirror_authority/"',
    )
    findings = [
        f"Wave 1 compatibility maintenance drift: missing {anchor}"
        for anchor in required_scope
        if anchor not in scope_text
    ]
    if "implementation/wave-2/README.md" not in test_text or "escapes authorized path set" not in test_text:
        findings.append("Wave 1 compatibility maintenance must still falsify Wave 2 as hypothetical Wave 1 scope")
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
        _execution_boundary_findings,
        _reconciliation_authority_boundary_findings,
        _sql_findings,
        _wave1_compatibility_maintenance_findings,
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