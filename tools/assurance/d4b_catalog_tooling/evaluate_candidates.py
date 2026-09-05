#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Optional, Tuple


class EvidenceViolation(RuntimeError):
    pass


class DuplicateMemberError(ValueError):
    pass


def _reject_duplicate_members(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMemberError(f"duplicate semantic manifest member: {key}")
        out[key] = value
    return out


def _canonical_semantic_manifest_bytes(raw: str) -> bytes:
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_members)
    except (json.JSONDecodeError, DuplicateMemberError) as exc:
        raise EvidenceViolation("semantic manifest must be strict canonicalizable JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceViolation("semantic manifest must be an object")
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise EvidenceViolation("semantic manifest cannot be canonically encoded") from exc


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: Tuple[str, ...]
    authenticated: bool = True


@dataclass(frozen=True)
class LogicalContractIdentity:
    domain: str
    name: str
    family: str

    def canonical(self) -> str:
        for value in (self.domain, self.name, self.family):
            if (
                not value
                or len(value) > 96
                or "/" in value
                or any(ord(ch) < 0x20 for ch in value)
            ):
                raise EvidenceViolation("invalid or ambiguous logical contract identity")
        return f"{self.domain}/{self.name}/{self.family}"


@dataclass(frozen=True)
class HistoricalMetadata:
    reader_ref: str
    upcaster_ref: str
    comparison_profile_ref: str


@dataclass(frozen=True)
class ContractRevision:
    identity: LogicalContractIdentity
    revision: str
    payload_schema: str
    semantic_manifest: str
    historical_metadata: HistoricalMetadata
    reviewed_provenance: str

    @property
    def payload_schema_sha256(self) -> str:
        return sha256(self.payload_schema.encode("utf-8")).hexdigest()

    @property
    def semantic_manifest_sha256(self) -> str:
        return sha256(_canonical_semantic_manifest_bytes(self.semantic_manifest)).hexdigest()

    @property
    def reviewed_content_sha256(self) -> str:
        payload = "\n".join(
            [
                self.identity.canonical(),
                self.revision,
                self.payload_schema_sha256,
                self.semantic_manifest_sha256,
                self.historical_metadata.reader_ref,
                self.historical_metadata.upcaster_ref,
                self.historical_metadata.comparison_profile_ref,
                self.reviewed_provenance,
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProductMapping:
    product: str
    subject: str
    vendor_version: str
    vendor_id: str
    reviewed_content_sha256: str


READER_ROLE = "contract_reader"
REVIEWER_ROLE = "contract_reviewer"
REGISTRY_PUBLISHER_ROLE = "registry_publisher"


def require_role(principal: Principal, role: str) -> None:
    if not principal.authenticated or not principal.subject:
        raise EvidenceViolation("catalog access requires authenticated principal")
    if role not in principal.roles:
        raise EvidenceViolation(f"catalog access missing role: {role}")


def _validate_revision(revision: ContractRevision) -> None:
    revision.identity.canonical()
    if not revision.revision or len(revision.revision) > 64:
        raise EvidenceViolation("invalid evidence revision token")
    try:
        payload_schema_bytes = revision.payload_schema.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise EvidenceViolation("payload schema must be strict utf-8") from exc
    if not revision.payload_schema or len(payload_schema_bytes) > 16_384:
        raise EvidenceViolation("payload schema outside evidence bound")
    try:
        semantic_raw = revision.semantic_manifest.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise EvidenceViolation("semantic manifest must be strict utf-8") from exc
    if not revision.semantic_manifest or len(semantic_raw) > 16_384:
        raise EvidenceViolation("semantic manifest outside evidence bound")
    _canonical_semantic_manifest_bytes(revision.semantic_manifest)
    for ref in (
        revision.historical_metadata.reader_ref,
        revision.historical_metadata.upcaster_ref,
        revision.historical_metadata.comparison_profile_ref,
        revision.reviewed_provenance,
    ):
        if not ref or len(ref) > 256:
            raise EvidenceViolation("invalid provenance or historical metadata ref")


class ReviewedHistory:
    def __init__(self) -> None:
        self._history: Dict[str, Dict[str, ContractRevision]] = {}

    def commit(self, principal: Principal, revision: ContractRevision) -> ContractRevision:
        require_role(principal, REVIEWER_ROLE)
        _validate_revision(revision)
        key = revision.identity.canonical()
        family = self._history.setdefault(key, {})
        if revision.revision in family:
            existing = family[revision.revision]
            if existing != revision:
                raise EvidenceViolation("reviewed revision history is immutable")
            return existing
        family[revision.revision] = revision
        return revision

    def read(self, principal: Principal, identity: LogicalContractIdentity, revision: str) -> ContractRevision:
        require_role(principal, READER_ROLE)
        try:
            return self._history[identity.canonical()][revision]
        except KeyError as exc:
            raise EvidenceViolation("reviewed contract revision not found") from exc


class RegistryMirror:
    def __init__(self, product: str, reviewed_authority: ReviewedHistory) -> None:
        if not product or len(product) > 128:
            raise EvidenceViolation("invalid registry product label")
        self.product = product
        self.reviewed_authority = reviewed_authority
        self.available = True
        self._mappings: Dict[Tuple[str, str], ProductMapping] = {}

    def publish(
        self,
        principal: Principal,
        reviewed: ContractRevision,
        subject: str,
        vendor_version: str,
        vendor_id: str,
    ) -> ProductMapping:
        require_role(principal, REGISTRY_PUBLISHER_ROLE)
        if not self.available:
            raise EvidenceViolation("registry unavailable")
        for value in (subject, vendor_version, vendor_id):
            if not value or len(value) > 256:
                raise EvidenceViolation("invalid registry mapping metadata")
        committed = self.reviewed_authority.read(principal, reviewed.identity, reviewed.revision)
        if committed != reviewed or committed.reviewed_content_sha256 != reviewed.reviewed_content_sha256:
            raise EvidenceViolation("registry publish requires exact preexisting reviewed authority")
        key = (reviewed.identity.canonical(), reviewed.revision)
        mapping = ProductMapping(
            product=self.product,
            subject=subject,
            vendor_version=vendor_version,
            vendor_id=vendor_id,
            reviewed_content_sha256=reviewed.reviewed_content_sha256,
        )
        existing = self._mappings.get(key)
        if existing is not None:
            if existing != mapping:
                raise EvidenceViolation("registry mapping history is immutable for a reviewed revision")
            return existing
        self._mappings[key] = mapping
        return mapping

    def mapping(self, principal: Principal, reviewed: ContractRevision) -> ProductMapping:
        require_role(principal, READER_ROLE)
        if not self.available:
            raise EvidenceViolation("registry unavailable")
        committed = self.reviewed_authority.read(principal, reviewed.identity, reviewed.revision)
        if committed != reviewed:
            raise EvidenceViolation("registry mapping lookup requires exact reviewed revision")
        try:
            mapping = self._mappings[(reviewed.identity.canonical(), reviewed.revision)]
        except KeyError as exc:
            raise EvidenceViolation("registry mapping missing") from exc
        if mapping.reviewed_content_sha256 != reviewed.reviewed_content_sha256:
            raise EvidenceViolation("registry mapping content drift")
        return mapping


class CatalogProfile:
    def __init__(self, candidate: str, history: ReviewedHistory, registry: Optional[RegistryMirror] = None) -> None:
        self.candidate = candidate
        self.history = history
        self.registry = registry

    def resolve(self, principal: Principal, identity: LogicalContractIdentity, revision: str) -> ContractRevision:
        reviewed = self.history.read(principal, identity, revision)
        if self.candidate == "reviewed_git_catalog":
            return reviewed
        if self.registry is None:
            raise EvidenceViolation("registry-backed candidate missing registry surface")
        if self.registry.available:
            self.registry.mapping(principal, reviewed)
        return reviewed


def compatibility(old: ContractRevision, new: ContractRevision) -> str:
    if old.identity != new.identity:
        raise EvidenceViolation("compatibility cannot cross logical contract identity")
    _validate_revision(old)
    _validate_revision(new)
    if old.payload_schema_sha256 == new.payload_schema_sha256 and old.semantic_manifest_sha256 == new.semantic_manifest_sha256:
        return "equivalent"
    if old.semantic_manifest_sha256 != new.semantic_manifest_sha256:
        return "semantic_review_required_breaking_until_proven_otherwise"
    return "payload_schema_change_requires_compatibility_review"


def assert_metadata_recoverable(revision: ContractRevision) -> None:
    metadata = revision.historical_metadata
    if not metadata.reader_ref or not metadata.upcaster_ref or not metadata.comparison_profile_ref:
        raise EvidenceViolation("historical interpretation metadata missing")


def candidate_fixture(candidate: str) -> Tuple[CatalogProfile, Principal, Principal, ContractRevision, ContractRevision]:
    reviewer = Principal("reviewer:axis-b", (REVIEWER_ROLE, READER_ROLE, REGISTRY_PUBLISHER_ROLE))
    reader = Principal("reader:axis-b", (READER_ROLE,))
    identity = LogicalContractIdentity("monitoring", "event.created", "canonical")
    v1 = ContractRevision(
        identity=identity,
        revision="fixture-r1",
        payload_schema='{"fields":["tenant_id","event_type","payload"]}',
        semantic_manifest='{"tenant_authority":"tenant_id","event_identity":"message_id","delivery":"at_least_once"}',
        historical_metadata=HistoricalMetadata("reader:event:v1", "upcaster:none", "compare:event:v1"),
        reviewed_provenance="git:fixture-commit-a",
    )
    v2 = ContractRevision(
        identity=identity,
        revision="fixture-r2",
        payload_schema=v1.payload_schema,
        semantic_manifest='{"tenant_authority":"tenant_id","event_identity":"provider_event_id","delivery":"at_least_once"}',
        historical_metadata=HistoricalMetadata("reader:event:v2", "upcaster:event:v1-to-v2", "compare:event:v2"),
        reviewed_provenance="git:fixture-commit-b",
    )
    history = ReviewedHistory()
    history.commit(reviewer, v1)
    history.commit(reviewer, v2)
    registry = None if candidate == "reviewed_git_catalog" else RegistryMirror("registry-fixture-a", history)
    profile = CatalogProfile(candidate, history, registry)
    if registry:
        registry.publish(reviewer, v1, "event-created", "17", "vendor-abc")
        registry.publish(reviewer, v2, "event-created", "18", "vendor-def")
    return profile, reviewer, reader, v1, v2


def exercise_candidate(candidate: str) -> None:
    profile, reviewer, reader, v1, v2 = candidate_fixture(candidate)
    assert profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256 == v1.reviewed_content_sha256
    assert profile.resolve(reader, v2.identity, v2.revision).reviewed_provenance == "git:fixture-commit-b"
    assert_metadata_recoverable(v1)
    assert_metadata_recoverable(v2)

    v1_reformatted = ContractRevision(
        identity=v1.identity,
        revision="fixture-r1-reformatted",
        payload_schema=v1.payload_schema,
        semantic_manifest='{ "delivery": "at_least_once", "event_identity": "message_id", "tenant_authority": "tenant_id" }',
        historical_metadata=v1.historical_metadata,
        reviewed_provenance="git:fixture-commit-reformatted",
    )
    assert v1.semantic_manifest_sha256 == v1_reformatted.semantic_manifest_sha256

    assert v1.payload_schema_sha256 == v2.payload_schema_sha256
    assert compatibility(v1, v2) == "semantic_review_required_breaking_until_proven_otherwise"

    ambiguous_identity = LogicalContractIdentity("monitoring/legacy", "event.created", "canonical")
    try:
        ambiguous_identity.canonical()
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("ambiguous logical contract identity delimiter was not blocked")

    rebound = ContractRevision(
        identity=v1.identity,
        revision=v1.revision,
        payload_schema=v1.payload_schema,
        semantic_manifest='{"tenant_authority":"provider_tenant"}',
        historical_metadata=v1.historical_metadata,
        reviewed_provenance="git:malicious-rebind",
    )
    try:
        profile.history.commit(reviewer, rebound)
    except EvidenceViolation:
        pass
    else:
        raise AssertionError("reviewed history overwrite was not blocked")

    for principal in (Principal("", (), authenticated=False), Principal("reader-no-role", ())):
        try:
            profile.history.read(principal, v1.identity, v1.revision)
        except EvidenceViolation:
            pass
        else:
            raise AssertionError("unauthorized direct history read was not blocked")
        try:
            profile.resolve(principal, v1.identity, v1.revision)
        except EvidenceViolation:
            pass
        else:
            raise AssertionError("unauthorized catalog read was not blocked")

    if profile.registry:
        unreviewed = ContractRevision(
            identity=v1.identity,
            revision="fixture-unreviewed",
            payload_schema=v1.payload_schema,
            semantic_manifest=v1.semantic_manifest,
            historical_metadata=v1.historical_metadata,
            reviewed_provenance="git:not-committed",
        )
        try:
            profile.registry.publish(reviewer, unreviewed, "event-created", "19", "vendor-unreviewed")
        except EvidenceViolation:
            pass
        else:
            raise AssertionError("registry accepted unreviewed contract authority")

        fake_provenance = ContractRevision(
            identity=v1.identity,
            revision=v1.revision,
            payload_schema=v1.payload_schema,
            semantic_manifest=v1.semantic_manifest,
            historical_metadata=v1.historical_metadata,
            reviewed_provenance="git:forged-provenance",
        )
        try:
            profile.registry.publish(reviewer, fake_provenance, "event-created", "20", "vendor-forged")
        except EvidenceViolation:
            pass
        else:
            raise AssertionError("registry accepted forged reviewed provenance")

        original_mapping = profile.registry.publish(reviewer, v1, "event-created", "17", "vendor-abc")
        assert original_mapping == profile.registry.mapping(reader, v1)
        try:
            profile.registry.publish(reviewer, v1, "renamed-in-place", "99", "vendor-rebind")
        except EvidenceViolation:
            pass
        else:
            raise AssertionError("registry mapping provenance overwrite was not blocked")

        before = profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256
        profile.registry.available = False
        during = profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256
        assert before == during == v1.reviewed_content_sha256
        profile.registry.available = True

        replacement = RegistryMirror("registry-fixture-b", profile.history)
        replacement.publish(reviewer, v1, "renamed-subject", "1", "other-vendor-001")
        old_map = profile.registry.mapping(reader, v1)
        new_map = replacement.mapping(reader, v1)
        assert old_map.vendor_id != new_map.vendor_id
        assert old_map.product != new_map.product
        assert old_map.reviewed_content_sha256 == new_map.reviewed_content_sha256 == v1.reviewed_content_sha256
        assert v1.identity.canonical() == "monitoring/event.created/canonical"


def main() -> None:
    candidates = (
        "reviewed_git_catalog",
        "registry_backed_catalog",
        "hybrid_reviewed_git_plus_registry_catalog",
    )
    for candidate in candidates:
        exercise_candidate(candidate)
    print(
        "d4b_catalog_tooling_candidate_source=PASS "
        "candidates=3 reviewed_authority=preexisting provenance=content_bound history=append_only "
        "semantic_manifest=canonical_and_compared mapping_history=immutable identity=unambiguous "
        "historical_metadata=recoverable authz=all_reads_fail_closed outage=meaning_stable "
        "product_identity=non_authoritative selection=not_selected ledger_credit=0"
    )


if __name__ == "__main__":
    main()
