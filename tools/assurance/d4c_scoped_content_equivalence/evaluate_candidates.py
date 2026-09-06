#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping

CANDIDATES = (
    "canonical_collision_resistant_fingerprint_profile",
    "keyed_authenticated_digest_profile",
    "protected_retained_immutable_original_profile",
    "hybrid_equivalence_authority_profile",
)
ELIGIBLE = "eligible_for_evidence_execution"
INELIGIBLE = "ineligible_by_contract"
INSUFFICIENT = "insufficient_evidence"
PROFILE_V1 = "equivalence/v1"
PROFILE_V2 = "equivalence/v2"
KEY_V1 = "fixture-verifier-key/v1"
KEY_V2 = "fixture-verifier-key/v2"
TEST_LIMIT_PROFILE = "scoped_equivalence_fixture_only_noncanonical"
TEST_MAX_CANONICAL_BYTES = 2048
TEST_KEYRING = {
    KEY_V1: b"fixture-root-secret-v1-not-production",
    KEY_V2: b"fixture-root-secret-v2-not-production",
}
TEST_OPERATION_SECRET = b"fixture-operation-secret-not-production"
IMMUTABLE_FIELDS = (
    "tenant_id",
    "message_type",
    "contract_version",
    "occurred_at",
    "payload",
)


class EvidenceViolation(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = False


@dataclass(frozen=True)
class Identity:
    consumer_contract: str
    trusted_message_identity_scope: str
    message_id: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.consumer_contract, self.trusted_message_identity_scope, self.message_id)


@dataclass(frozen=True)
class CandidatePolicy:
    name: str
    evidence_mode: str
    retains_original: bool
    keyed: bool


@dataclass(frozen=True)
class EvidenceRecord:
    profile_version: str
    evidence_mode: str
    key_version: str | None
    digest_hex: str | None
    retained_original: bytes | None

    def authority_surface(self) -> Dict[str, Any]:
        return {
            "profile_version": self.profile_version,
            "evidence_mode": self.evidence_mode,
            "key_version": self.key_version,
            "digest_hex": self.digest_hex,
            "has_retained_original": self.retained_original is not None,
        }


@dataclass(frozen=True)
class CoResidentEntry:
    evidence: EvidenceRecord
    effect_completion: str


POLICIES = {
    "canonical_collision_resistant_fingerprint_profile": CandidatePolicy(
        "canonical_collision_resistant_fingerprint_profile", "sha256", False, False
    ),
    "keyed_authenticated_digest_profile": CandidatePolicy(
        "keyed_authenticated_digest_profile", "hmac_sha256", False, True
    ),
    "protected_retained_immutable_original_profile": CandidatePolicy(
        "protected_retained_immutable_original_profile", "protected_original", True, False
    ),
    "hybrid_equivalence_authority_profile": CandidatePolicy(
        "hybrid_equivalence_authority_profile", "hybrid_hmac_plus_original", True, True
    ),
}


def policy_for(candidate: str) -> CandidatePolicy:
    try:
        return POLICIES[candidate]
    except KeyError as exc:
        raise ValueError(candidate) from exc


def validate_structured_value(value: Any) -> None:
    stack = [value]
    while stack:
        node = stack.pop()
        if node is None or isinstance(node, (bool, int, str)):
            continue
        if isinstance(node, float):
            raise EvidenceViolation("ambiguous_numeric_semantics")
        if isinstance(node, list):
            stack.extend(node)
            continue
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str):
                    raise EvidenceViolation("non_string_semantic_key")
                stack.append(child)
            continue
        raise EvidenceViolation("unsupported_semantic_type")


def canonical_semantic_bytes(immutable: Mapping[str, Any]) -> bytes:
    projection: Dict[str, Any] = {}
    for field in IMMUTABLE_FIELDS:
        if field not in immutable:
            raise EvidenceViolation("immutable_semantic_field_missing")
        projection[field] = immutable[field]
    validate_structured_value(projection)
    encoder = json.JSONEncoder(
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    out = bytearray()
    for text in encoder.iterencode(projection):
        chunk = text.encode("utf-8")
        if len(out) + len(chunk) > TEST_MAX_CANONICAL_BYTES:
            raise EvidenceViolation("verification_work_exceeded")
        out.extend(chunk)
    return bytes(out)


def scope_key(identity: Identity, key_version: str) -> bytes:
    secret = TEST_KEYRING[key_version]
    scope_material = (
        identity.consumer_contract + "\x1f" + identity.trusted_message_identity_scope
    ).encode("utf-8")
    return hmac.new(secret, scope_material, hashlib.sha256).digest()


def digest_for(
    policy: CandidatePolicy,
    identity: Identity,
    canonical: bytes,
    *,
    key_version: str | None,
) -> str | None:
    if policy.evidence_mode == "sha256":
        return hashlib.sha256(canonical).hexdigest()
    if policy.keyed:
        if key_version not in TEST_KEYRING:
            raise EvidenceViolation("historical_verifier_key_unavailable")
        return hmac.new(scope_key(identity, key_version), canonical, hashlib.sha256).hexdigest()
    return None


def build_record(policy: CandidatePolicy, identity: Identity, canonical: bytes) -> EvidenceRecord:
    key_version = KEY_V1 if policy.keyed else None
    return EvidenceRecord(
        profile_version=PROFILE_V1,
        evidence_mode=policy.evidence_mode,
        key_version=key_version,
        digest_hex=digest_for(policy, identity, canonical, key_version=key_version),
        retained_original=canonical if policy.retains_original else None,
    )


def compare_record(
    policy: CandidatePolicy,
    identity: Identity,
    record: EvidenceRecord,
    canonical: bytes,
    *,
    comparison_access: bool,
) -> str:
    if not comparison_access:
        return "uncertain_access_denied"
    if record.profile_version not in {PROFILE_V1, PROFILE_V2}:
        return "uncertain_unverifiable_profile"
    if record.evidence_mode != policy.evidence_mode:
        return "uncertain_profile_mismatch"
    matched = True
    if policy.keyed:
        if record.key_version not in TEST_KEYRING:
            return "uncertain_unverifiable_key"
        expected = digest_for(
            policy,
            identity,
            canonical,
            key_version=record.key_version,
        )
        matched = matched and expected is not None and hmac.compare_digest(record.digest_hex or "", expected)
    if policy.retains_original and record.retained_original is not None:
        matched = matched and hmac.compare_digest(record.retained_original, canonical)
    elif policy.retains_original and record.digest_hex is None:
        return "uncertain_equivalence_authority_missing"
    return "benign_duplicate" if matched else "integrity_conflict"


class EquivalenceEngine:
    def __init__(self, candidate: str) -> None:
        self.policy = policy_for(candidate)
        self._co_resident: Dict[tuple[str, str, str], CoResidentEntry] = {}
        self.external_results: Dict[str, str] = {}

    @property
    def records(self) -> Dict[tuple[str, str, str], EvidenceRecord]:
        return {key: entry.evidence for key, entry in self._co_resident.items()}

    @property
    def effects(self) -> Dict[tuple[str, str, str], str]:
        return {key: entry.effect_completion for key, entry in self._co_resident.items()}

    def _record(self, identity: Identity) -> EvidenceRecord:
        return self._co_resident[identity.key].evidence

    def _replace_record(self, identity: Identity, record: EvidenceRecord) -> None:
        entry = self._co_resident[identity.key]
        self._co_resident[identity.key] = replace(entry, evidence=record)

    @staticmethod
    def _require_trusted_identity(
        identity: Identity,
        *,
        trusted_consumer_contract: bool,
        trusted_message_scope: bool,
    ) -> None:
        if not trusted_consumer_contract:
            raise EvidenceViolation("untrusted_consumer_contract")
        if not trusted_message_scope:
            raise EvidenceViolation("untrusted_message_identity_scope")
        if not all(identity.key):
            raise EvidenceViolation("invalid_scoped_message_identity")

    def classify_or_commit(
        self,
        identity: Identity,
        immutable: Mapping[str, Any],
        *,
        trusted_consumer_contract: bool = True,
        trusted_message_scope: bool = True,
        comparison_access: bool = True,
        fail_co_resident_effect: bool = False,
    ) -> str:
        self._require_trusted_identity(
            identity,
            trusted_consumer_contract=trusted_consumer_contract,
            trusted_message_scope=trusted_message_scope,
        )
        canonical = canonical_semantic_bytes(immutable)
        existing = self._co_resident.get(identity.key)
        if existing is not None:
            return compare_record(
                self.policy,
                identity,
                existing.evidence,
                canonical,
                comparison_access=comparison_access,
            )

        record = build_record(self.policy, identity, canonical)
        if fail_co_resident_effect:
            return "co_resident_effect_rolled_back"
        self._co_resident[identity.key] = CoResidentEntry(
            evidence=record,
            effect_completion="effect_completed",
        )
        return "new_effect_committed"

    def classify_missing(self, identity: Identity, immutable: Mapping[str, Any]) -> str:
        self._require_trusted_identity(
            identity,
            trusted_consumer_contract=True,
            trusted_message_scope=True,
        )
        canonical_semantic_bytes(immutable)
        if identity.key not in self._co_resident:
            return "uncertain_equivalence_evidence_missing"
        raise AssertionError("fixture expected missing evidence")

    def erase_payload_authority(self, identity: Identity) -> bool:
        record = self._record(identity)
        if record.retained_original is None:
            return record.digest_hex is not None
        if record.digest_hex is None:
            return False
        self._replace_record(identity, replace(record, retained_original=None))
        return True

    def tamper_profile(self, identity: Identity) -> None:
        self._replace_record(
            identity,
            replace(self._record(identity), profile_version="equivalence/unknown"),
        )

    def tamper_key_version(self, identity: Identity) -> None:
        self._replace_record(
            identity,
            replace(self._record(identity), key_version="fixture-verifier-key/retired"),
        )

    def equality_preserving_migrate(self, identity: Identity) -> bool:
        record = self._record(identity)
        if record.profile_version != PROFILE_V1:
            return False
        if self.policy.keyed and self.policy.retains_original and record.retained_original is not None:
            migrated = replace(
                record,
                profile_version=PROFILE_V2,
                key_version=KEY_V2,
                digest_hex=digest_for(
                    self.policy,
                    identity,
                    record.retained_original,
                    key_version=KEY_V2,
                ),
            )
        else:
            migrated = replace(record, profile_version=PROFILE_V2)
        self._replace_record(identity, migrated)
        if self.policy.retains_original and record.retained_original is not None:
            return compare_record(
                self.policy,
                identity,
                migrated,
                record.retained_original,
                comparison_access=True,
            ) == "benign_duplicate"
        return migrated.key_version == record.key_version and migrated.digest_hex == record.digest_hex

    def stable_external_operation_id(self, identity: Identity) -> str:
        material = "\x1f".join(identity.key).encode("utf-8")
        return hmac.new(TEST_OPERATION_SECRET, material, hashlib.sha256).hexdigest()

    def reconcile_external_effect(self, identity: Identity, result: str) -> tuple[str, str]:
        operation_id = self.stable_external_operation_id(identity)
        prior = self.external_results.setdefault(operation_id, result)
        return operation_id, prior

    def exposed_comparison_evidence(self, identity: Identity, *, comparison_access: bool) -> str | None:
        if not comparison_access:
            return None
        return self._record(identity).digest_hex


def base_event(secret_value: str = "yes") -> Dict[str, Any]:
    return {
        "tenant_id": "tenant-a",
        "message_type": "ticket.changed",
        "contract_version": 3,
        "occurred_at": "2026-09-06T00:00:00Z",
        "payload": {"approved": secret_value, "count": 1},
    }


class ExplodingImmutable(dict):
    def __contains__(self, key: object) -> bool:
        raise AssertionError("semantic content inspected before trust admission")


def check_candidate(candidate: str) -> Dict[str, bool]:
    policy = policy_for(candidate)
    identity = Identity("ticket-projection/v3", "tenant-a:cell-1", "msg-001")
    engine = EquivalenceEngine(candidate)
    first = engine.classify_or_commit(identity, base_event())
    repeated = engine.classify_or_commit(identity, base_event())

    conflicts = []
    for field in IMMUTABLE_FIELDS:
        changed = base_event()
        if field == "payload":
            changed[field] = {"approved": "no", "count": 1}
        elif field == "contract_version":
            changed[field] = 4
        else:
            changed[field] = str(changed[field]) + "-changed"
        conflicts.append(engine.classify_or_commit(identity, changed) == "integrity_conflict")

    scope_blocked = contract_blocked = False
    try:
        engine.classify_or_commit(
            Identity("ticket-projection/v3", "untrusted", "msg-u1"),
            ExplodingImmutable(),
            trusted_message_scope=False,
        )
    except EvidenceViolation as exc:
        scope_blocked = exc.code == "untrusted_message_identity_scope"
    try:
        engine.classify_or_commit(
            Identity("untrusted-contract", "tenant-a:cell-1", "msg-u2"),
            ExplodingImmutable(),
            trusted_consumer_contract=False,
        )
    except EvidenceViolation as exc:
        contract_blocked = exc.code == "untrusted_consumer_contract"

    missing_engine = EquivalenceEngine(candidate)
    missing = missing_engine.classify_missing(identity, base_event())

    profile_engine = EquivalenceEngine(candidate)
    profile_engine.classify_or_commit(identity, base_event())
    profile_engine.tamper_profile(identity)
    unverifiable_profile = profile_engine.classify_or_commit(identity, base_event())

    key_engine = EquivalenceEngine(candidate)
    key_engine.classify_or_commit(identity, base_event())
    if policy.keyed:
        key_engine.tamper_key_version(identity)
        unverifiable_key = key_engine.classify_or_commit(identity, base_event())
    else:
        unverifiable_key = "not_applicable"

    scope_b = Identity("ticket-projection/v3", "tenant-b:cell-1", "msg-001")
    engine_b = EquivalenceEngine(candidate)
    engine_b.classify_or_commit(scope_b, base_event())
    evidence_a = engine.exposed_comparison_evidence(identity, comparison_access=True)
    evidence_b = engine_b.exposed_comparison_evidence(scope_b, comparison_access=True)
    canonical_guess = canonical_semantic_bytes(base_event("yes"))
    if policy.evidence_mode == "sha256":
        guessed = hashlib.sha256(canonical_guess).hexdigest()
        confidentiality_ok = evidence_a != evidence_b and guessed != evidence_a
        dictionary_oracle_blocked = guessed != evidence_a
    elif policy.keyed:
        confidentiality_ok = evidence_a is not None and evidence_b is not None and evidence_a != evidence_b
        dictionary_oracle_blocked = True
    else:
        confidentiality_ok = evidence_a is None and evidence_b is None
        dictionary_oracle_blocked = True

    no_access = engine.exposed_comparison_evidence(identity, comparison_access=False) is None
    authority_surface = engine.records[identity.key].authority_surface()
    no_forbidden_authority = not ({"authorization", "routing", "ordering", "bearer"} & set(authority_surface))

    rollback_engine = EquivalenceEngine(candidate)
    rolled_back = rollback_engine.classify_or_commit(
        identity, base_event(), fail_co_resident_effect=True
    )
    atomic_rollback = (
        rolled_back == "co_resident_effect_rolled_back"
        and identity.key not in rollback_engine.records
        and identity.key not in rollback_engine.effects
    )
    committed_entry_is_atomic = (
        identity.key in engine.records
        and identity.key in engine.effects
        and set(engine.records) == set(engine.effects)
    )

    op1, result1 = engine.reconcile_external_effect(identity, "accepted")
    op2, result2 = engine.reconcile_external_effect(identity, "different-retry-result")
    stable_external = op1 == op2 and result1 == result2 == "accepted"

    history_engine = EquivalenceEngine(candidate)
    history_engine.classify_or_commit(identity, base_event())
    historical_before = history_engine.classify_or_commit(identity, base_event()) == "benign_duplicate"
    migration_ok = history_engine.equality_preserving_migrate(identity)
    historical_after = history_engine.classify_or_commit(identity, base_event()) == "benign_duplicate"
    record_after = history_engine.records[identity.key]
    verifier_generation_explicit = (not policy.keyed) or record_after.key_version in TEST_KEYRING

    erasure_engine = EquivalenceEngine(candidate)
    erasure_engine.classify_or_commit(identity, base_event())
    erasure_allowed = erasure_engine.erase_payload_authority(identity)
    erasure_safety = erasure_allowed is False if policy.evidence_mode == "protected_original" else erasure_allowed is True

    oversized = base_event("x" * (TEST_MAX_CANONICAL_BYTES + 128))
    bounded = False
    try:
        EquivalenceEngine(candidate).classify_or_commit(identity, oversized)
    except EvidenceViolation as exc:
        bounded = exc.code == "verification_work_exceeded" and exc.retryable is False

    access_result = engine.classify_or_commit(identity, base_event(), comparison_access=False)
    uncertainty_ok = missing == "uncertain_equivalence_evidence_missing" and unverifiable_profile == "uncertain_unverifiable_profile"
    if policy.keyed:
        uncertainty_ok = uncertainty_ok and unverifiable_key == "uncertain_unverifiable_key"

    return {
        "dedup_identity_is_scoped_tuple": identity.key == ("ticket-projection/v3", "tenant-a:cell-1", "msg-001"),
        "trusted_identity_precedes_equivalence_work": scope_blocked and contract_blocked,
        "durable_equal_repeat_is_benign_duplicate": first == "new_effect_committed" and repeated == "benign_duplicate",
        "all_required_immutable_semantic_fields_are_covered": all(conflicts),
        "conflicting_same_scoped_identity_fails_closed": all(conflicts),
        "same_canonical_interpretation_drives_validation_and_evidence": canonical_semantic_bytes(base_event()) == canonical_semantic_bytes(dict(reversed(list(base_event().items())))),
        "profile_version_is_explicit_and_historically_recoverable": historical_before and migration_ok and historical_after and verifier_generation_explicit,
        "low_entropy_confidentiality_is_scope_safe": confidentiality_ok and dictionary_oracle_blocked,
        "keyed_verifier_generation_is_explicit_and_recoverable": verifier_generation_explicit and ((not policy.keyed) or unverifiable_key == "uncertain_unverifiable_key"),
        "comparison_evidence_has_no_forbidden_authority": no_forbidden_authority,
        "co_resident_inbox_and_effect_are_atomic": atomic_rollback and committed_entry_is_atomic,
        "cross_authority_effect_uses_stable_operation_and_reconciliation": stable_external,
        "historical_authority_survives_or_migrates_equality_preserving": historical_before and historical_after,
        "payload_erasure_preserves_last_equivalence_authority": erasure_safety,
        "missing_or_unverifiable_evidence_is_uncertainty": uncertainty_ok,
        "verification_is_bounded_and_access_controlled": bounded and no_access and access_result == "uncertain_access_denied",
        "fixture_profile_is_noncanonical": TEST_LIMIT_PROFILE.endswith("_noncanonical"),
    }


def evaluate_all() -> Dict[str, Any]:
    checks = {candidate: check_candidate(candidate) for candidate in CANDIDATES}
    results: Dict[str, str] = {}
    for candidate in CANDIDATES:
        candidate_checks = checks[candidate]
        if not candidate_checks["low_entropy_confidentiality_is_scope_safe"]:
            results[candidate] = INELIGIBLE
        elif all(candidate_checks.values()):
            results[candidate] = ELIGIBLE
        else:
            results[candidate] = INSUFFICIENT
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-011",
        "evidence_id": "scoped_content_equivalence_confidentiality_and_conflict_rejection",
        "fixture_profile": TEST_LIMIT_PROFILE,
        "candidate_results": results,
        "equivalent_reviewed_profile": INSUFFICIENT,
        "checks": checks,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }


def main() -> int:
    result = evaluate_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    expected = {
        "canonical_collision_resistant_fingerprint_profile": INELIGIBLE,
        "keyed_authenticated_digest_profile": ELIGIBLE,
        "protected_retained_immutable_original_profile": ELIGIBLE,
        "hybrid_equivalence_authority_profile": ELIGIBLE,
    }
    return 0 if result["candidate_results"] == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
