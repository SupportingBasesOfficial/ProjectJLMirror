#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class ClassificationPolicy:
    classification: str
    require_protection: bool
    allow_logging: bool
    retention_class: str
    delivery_class: str

@dataclass(frozen=True)
class KeyAuthority:
    current_generation: int
    historical_generations: tuple[int, ...]
    authority_source: str = "secret_or_kms_authority"
    key_material_exportable: bool = False

@dataclass(frozen=True)
class ProtectedEvidence:
    scope: str
    comparison_profile: str
    key_generation_ref: int
    classification: str
    retained_reference_only: bool
    secret_material_present: bool = False

class ProtectionDenied(Exception):
    pass

def classify(classification: str) -> ClassificationPolicy:
    policies = {
        "restricted": ClassificationPolicy("restricted", True, False, "bounded_confidential", "protected_only"),
        "internal": ClassificationPolicy("internal", True, True, "bounded_internal", "protected_only"),
        "public": ClassificationPolicy("public", False, True, "bounded_public", "ordinary"),
    }
    if classification not in policies:
        raise ProtectionDenied("unknown data classification")
    return policies[classification]

def issue_evidence(*, authority: KeyAuthority, scope: str, classification: str, comparison_profile: str, authorized: bool, minimized: bool) -> ProtectedEvidence:
    policy = classify(classification)
    if authority.authority_source != "secret_or_kms_authority" or authority.key_material_exportable:
        raise ProtectionDenied("key material must remain behind secret/KMS authority")
    if not authorized:
        raise ProtectionDenied("encryption does not replace authorization")
    if not minimized:
        raise ProtectionDenied("encryption does not replace minimization")
    if not scope or not comparison_profile:
        raise ProtectionDenied("scope/profile required")
    if policy.require_protection and policy.delivery_class != "protected_only":
        raise ProtectionDenied("classification policy weakened")
    return ProtectedEvidence(
        scope=scope,
        comparison_profile=comparison_profile,
        key_generation_ref=authority.current_generation,
        classification=classification,
        retained_reference_only=True,
        secret_material_present=False,
    )

def historical_verifier_available(evidence: ProtectedEvidence, authority: KeyAuthority) -> bool:
    return (
        authority.authority_source == "secret_or_kms_authority"
        and not authority.key_material_exportable
        and evidence.retained_reference_only
        and not evidence.secret_material_present
        and evidence.key_generation_ref in authority.historical_generations
    )

def duplicate_sensitive_effect_eligible(evidence: ProtectedEvidence, authority: KeyAuthority, *, scope: str, profile: str) -> bool:
    if evidence.scope != scope or evidence.comparison_profile != profile:
        return False
    return historical_verifier_available(evidence, authority)

def rotate(authority: KeyAuthority, new_generation: int) -> KeyAuthority:
    if new_generation <= authority.current_generation:
        raise ProtectionDenied("rotation must advance generation")
    history = tuple(sorted(set(authority.historical_generations + (authority.current_generation, new_generation))))
    return KeyAuthority(new_generation, history, authority.authority_source, authority.key_material_exportable)

def equality_preserving_migrate(evidence: ProtectedEvidence, authority: KeyAuthority, *, target_generation: int) -> ProtectedEvidence:
    if not historical_verifier_available(evidence, authority):
        raise ProtectionDenied("cannot migrate without valid historical verifier")
    if target_generation not in authority.historical_generations:
        raise ProtectionDenied("target generation unavailable")
    return replace(evidence, key_generation_ref=target_generation)

def restored_verifier_can_become_current(*, restored_generation: int, authority: KeyAuthority, evidence_scope: str, requested_scope: str) -> bool:
    if restored_generation != authority.current_generation:
        return False
    return evidence_scope == requested_scope

def run_probes() -> dict[str, bool]:
    authority = KeyAuthority(current_generation=7, historical_generations=(5, 6, 7))
    evidence = issue_evidence(
        authority=authority,
        scope="tenant-a/orders/consumer-inbox",
        classification="restricted",
        comparison_profile="semantic-equivalence-v3",
        authorized=True,
        minimized=True,
    )
    policy = classify("restricted")
    checks: dict[str, bool] = {
        "classification_controls_protection_storage_delivery_logging_retention": policy.require_protection and not policy.allow_logging and policy.retention_class == "bounded_confidential" and policy.delivery_class == "protected_only",
        "key_material_stays_behind_secret_kms": authority.authority_source == "secret_or_kms_authority" and not authority.key_material_exportable,
        "retained_evidence_is_non_secret_reference_only": evidence.retained_reference_only and not evidence.secret_material_present and evidence.key_generation_ref == 7,
        "historical_verifier_available": historical_verifier_available(evidence, authority),
        "duplicate_sensitive_effect_accepts_known_historical_generation": duplicate_sensitive_effect_eligible(evidence, authority, scope=evidence.scope, profile=evidence.comparison_profile),
    }

    missing = KeyAuthority(current_generation=7, historical_generations=(6, 7))
    checks["verifier_loss_fails_closed"] = not duplicate_sensitive_effect_eligible(evidence, missing, scope=evidence.scope, profile=evidence.comparison_profile)
    unknown = replace(evidence, key_generation_ref=99)
    checks["unknown_generation_fails_closed"] = not duplicate_sensitive_effect_eligible(unknown, authority, scope=evidence.scope, profile=evidence.comparison_profile)
    checks["scope_mismatch_fails_closed"] = not duplicate_sensitive_effect_eligible(evidence, authority, scope="tenant-b/orders/consumer-inbox", profile=evidence.comparison_profile)
    checks["profile_mismatch_fails_closed"] = not duplicate_sensitive_effect_eligible(evidence, authority, scope=evidence.scope, profile="semantic-equivalence-v4")

    rotated = rotate(authority, 8)
    checks["rotation_preserves_historical_verifier"] = rotated.current_generation == 8 and duplicate_sensitive_effect_eligible(evidence, rotated, scope=evidence.scope, profile=evidence.comparison_profile)
    migrated = equality_preserving_migrate(evidence, rotated, target_generation=8)
    checks["equality_preserving_migration_preserves_scope_profile"] = migrated.scope == evidence.scope and migrated.comparison_profile == evidence.comparison_profile and migrated.key_generation_ref == 8 and not migrated.secret_material_present
    checks["migrated_evidence_verifies"] = duplicate_sensitive_effect_eligible(migrated, rotated, scope=evidence.scope, profile=evidence.comparison_profile)
    checks["restored_old_verifier_cannot_become_current"] = not restored_verifier_can_become_current(restored_generation=7, authority=rotated, evidence_scope=evidence.scope, requested_scope=evidence.scope)
    checks["restored_profile_cannot_authorize_unrelated_scope"] = not restored_verifier_can_become_current(restored_generation=8, authority=rotated, evidence_scope=evidence.scope, requested_scope="tenant-b/orders/consumer-inbox")

    for name, authorized, minimized in [
        ("encryption_does_not_replace_authorization", False, True),
        ("encryption_does_not_replace_minimization", True, False),
    ]:
        try:
            issue_evidence(authority=authority, scope=evidence.scope, classification="restricted", comparison_profile=evidence.comparison_profile, authorized=authorized, minimized=minimized)
            checks[name] = False
        except ProtectionDenied:
            checks[name] = True

    exportable = KeyAuthority(current_generation=7, historical_generations=(7,), key_material_exportable=True)
    try:
        issue_evidence(authority=exportable, scope=evidence.scope, classification="restricted", comparison_profile=evidence.comparison_profile, authorized=True, minimized=True)
        checks["exportable_key_material_rejected"] = False
    except ProtectionDenied:
        checks["exportable_key_material_rejected"] = True

    return checks

if __name__ == "__main__":
    checks = run_probes()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("FAILED: " + ",".join(failed))
    print(f"d4d_open_evt_017_message_protection_source=PASS probes={len(checks)}")
