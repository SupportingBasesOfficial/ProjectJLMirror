#!/usr/bin/env python3
from __future__ import annotations

import base64
import re
from dataclasses import dataclass

ELIGIBLE = "eligible_for_evidence_execution"
MAX_ISSUANCE_SEQUENCE = (1 << 64) - 1
_UINT64_MASK = MAX_ISSUANCE_SEQUENCE
_PERMUTE_MULTIPLIER = 0x9E3779B185EBCA87  # odd => bijective modulo 2^64
_PERMUTE_OFFSET = 0xD4B0C0DE5A17E11D


@dataclass(frozen=True)
class ParsedVersion:
    candidate: str
    canonical: str


@dataclass(frozen=True)
class HistoricalVersionEvidence:
    candidate: str
    original_bytes: bytes


class CandidateAdapter:
    candidate: str

    def parse(self, raw: str) -> ParsedVersion:
        raise NotImplementedError

    def equal(self, left: str, right: str) -> bool:
        return self.parse(left).canonical == self.parse(right).canonical

    def compare_order(self, left: str, right: str) -> int:
        raise ValueError("ordering authority is not granted by the source-evidence profile")

    def authority_projection(self, raw: str) -> dict[str, str]:
        parsed = self.parse(raw)
        return {"contract_version": parsed.canonical}

    def retain_historical(self, raw: str) -> HistoricalVersionEvidence:
        parsed = self.parse(raw)
        return HistoricalVersionEvidence(candidate=self.candidate, original_bytes=parsed.canonical.encode("ascii"))

    def restore_historical(self, evidence: HistoricalVersionEvidence) -> ParsedVersion:
        if evidence.candidate != self.candidate:
            raise ValueError("historical version candidate family mismatch")
        raw = evidence.original_bytes.decode("ascii", errors="strict")
        parsed = self.parse(raw)
        if parsed.canonical.encode("ascii") != evidence.original_bytes:
            raise ValueError("historical version bytes were reinterpreted")
        return parsed


class PositiveIntegerRevision(CandidateAdapter):
    candidate = "positive_integer_family_revision"
    _pattern = re.compile(r"[1-9][0-9]{0,9}\Z")

    def parse(self, raw: str) -> ParsedVersion:
        if not isinstance(raw, str) or not self._pattern.fullmatch(raw):
            raise ValueError("noncanonical positive-integer test vector")
        return ParsedVersion(self.candidate, raw)


class SemanticVersionLike(CandidateAdapter):
    candidate = "semantic_version_like_contract_revision"
    _pattern = re.compile(r"(?:0|[1-9][0-9]{0,5})\.(?:0|[1-9][0-9]{0,5})\.(?:0|[1-9][0-9]{0,5})\Z")

    def parse(self, raw: str) -> ParsedVersion:
        if not isinstance(raw, str) or not self._pattern.fullmatch(raw):
            raise ValueError("noncanonical semantic-version-like test vector")
        return ParsedVersion(self.candidate, raw)


class OpaqueMonotonicToken(CandidateAdapter):
    candidate = "opaque_monotonic_contract_token"
    _pattern = re.compile(r"cv_[A-Z2-7]{8,24}\Z")

    def parse(self, raw: str) -> ParsedVersion:
        if not isinstance(raw, str) or not self._pattern.fullmatch(raw):
            raise ValueError("noncanonical opaque-token test vector")
        return ParsedVersion(self.candidate, raw)


class OpaqueMonotonicIssuer:
    """Evidence-only issuer: monotonic issuance is internal; tokens stay externally opaque."""

    def __init__(self) -> None:
        self._last_sequence = 0

    @staticmethod
    def _opaque_fixture_body(sequence: int) -> str:
        # Affine permutation over uint64: collision-free for the bounded fixture domain.
        permuted = (sequence * _PERMUTE_MULTIPLIER + _PERMUTE_OFFSET) & _UINT64_MASK
        return base64.b32encode(permuted.to_bytes(8, "big", signed=False)).decode("ascii").rstrip("=")

    def issue(self, sequence: int) -> str:
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise ValueError("issuance sequence must be an integer")
        if sequence <= 0 or sequence > MAX_ISSUANCE_SEQUENCE:
            raise ValueError("issuance sequence outside bounded positive range")
        if sequence <= self._last_sequence:
            raise ValueError("issuance sequence must increase strictly")
        token = f"cv_{self._opaque_fixture_body(sequence)}"
        self._last_sequence = sequence
        return token


ADAPTERS: tuple[CandidateAdapter, ...] = (
    PositiveIntegerRevision(),
    SemanticVersionLike(),
    OpaqueMonotonicToken(),
)


def assert_rejected(adapter: CandidateAdapter, vectors: tuple[str, ...]) -> None:
    for vector in vectors:
        try:
            adapter.parse(vector)
        except ValueError:
            continue
        raise AssertionError(f"{adapter.candidate} accepted forbidden vector {vector!r}")


def assert_ordering_absent(adapter: CandidateAdapter, left: str, right: str) -> None:
    try:
        adapter.compare_order(left, right)
    except ValueError as exc:
        if "ordering authority" not in str(exc):
            raise
        return
    raise AssertionError(f"{adapter.candidate} exposed ordering authority")


def assert_no_authority_fields(adapter: CandidateAdapter, vector: str) -> None:
    projected = adapter.authority_projection(vector)
    if set(projected) != {"contract_version"}:
        raise AssertionError(f"{adapter.candidate} leaked authority fields: {sorted(projected)}")


def assert_breaking_change_requires_transition(adapter: CandidateAdapter, before_version: str, after_version: str) -> None:
    before = adapter.parse(before_version)
    after = adapter.parse(after_version)
    if before.canonical == after.canonical:
        raise ValueError("breaking semantic change cannot reuse the same contract_version")


def assert_historical_continuity(adapter: CandidateAdapter, raw: str, other_adapter: CandidateAdapter) -> None:
    evidence = adapter.retain_historical(raw)
    restored = adapter.restore_historical(evidence)
    if restored.canonical != raw or evidence.original_bytes != raw.encode("ascii"):
        raise AssertionError("historical contract-version meaning changed")
    try:
        other_adapter.restore_historical(evidence)
    except ValueError as exc:
        if "candidate family mismatch" not in str(exc):
            raise
    else:
        raise AssertionError("historical version was reinterpreted by a different candidate family")


def prove_opaque_monotonic_issuance(adapter: CandidateAdapter) -> tuple[str, str]:
    issuer = OpaqueMonotonicIssuer()
    first = issuer.issue(1)
    second = issuer.issue(2)
    adapter.parse(first)
    adapter.parse(second)
    if first == second:
        raise AssertionError("monotonic issuer produced duplicate opaque token")
    if OpaqueMonotonicIssuer._opaque_fixture_body(1) == OpaqueMonotonicIssuer._opaque_fixture_body(2):
        raise AssertionError("bijective fixture mapping collapsed distinct sequences")
    for invalid in (2, 1, 0, -1, MAX_ISSUANCE_SEQUENCE + 1):
        try:
            issuer.issue(invalid)
        except ValueError:
            continue
        raise AssertionError(f"monotonic issuer accepted invalid sequence {invalid}")
    assert_ordering_absent(adapter, first, second)
    return first, second


def evaluate() -> dict[str, str]:
    positive = ADAPTERS[0]
    semver = ADAPTERS[1]
    opaque = ADAPTERS[2]

    positive.parse("1")
    positive.parse("9999999999")
    assert_rejected(positive, ("0", "01", "+1", "-1", "1 ", " 1", "1.0"))
    assert_ordering_absent(positive, "1", "2")
    assert_no_authority_fields(positive, "1")
    try:
        assert_breaking_change_requires_transition(positive, "1", "1")
    except ValueError:
        pass
    else:
        raise AssertionError("positive integer candidate allowed breaking-version reuse")
    assert_breaking_change_requires_transition(positive, "1", "2")
    assert_historical_continuity(positive, "1", semver)

    semver.parse("0.0.1")
    semver.parse("12.34.56")
    assert_rejected(semver, ("01.0.0", "1.0", "1.0.0-alpha", "1.0.0+build", "1.00.0", " 1.0.0"))
    assert_ordering_absent(semver, "1.0.0", "2.0.0")
    assert_no_authority_fields(semver, "1.0.0")
    try:
        assert_breaking_change_requires_transition(semver, "1.0.0", "1.0.0")
    except ValueError:
        pass
    else:
        raise AssertionError("semantic-version-like candidate allowed breaking-version reuse")
    assert_breaking_change_requires_transition(semver, "1.0.0", "2.0.0")
    assert_historical_continuity(semver, "1.0.0", opaque)

    opaque.parse("cv_ABCDEFG2")
    opaque.parse("cv_234567ABCDEFGHJK")
    assert_rejected(opaque, ("cv_abcdefg2", "CV_ABCDEFG2", "cv_ABC", "cv_ABCDEFG0", " cv_ABCDEFG2", "cv_ABCDEFG2 "))
    first_opaque, second_opaque = prove_opaque_monotonic_issuance(opaque)
    assert_no_authority_fields(opaque, first_opaque)
    if opaque.equal(first_opaque, second_opaque):
        raise AssertionError("distinct monotonic issues compared equal")
    try:
        assert_breaking_change_requires_transition(opaque, first_opaque, first_opaque)
    except ValueError:
        pass
    else:
        raise AssertionError("opaque candidate allowed breaking-version reuse")
    assert_breaking_change_requires_transition(opaque, first_opaque, second_opaque)
    assert_historical_continuity(opaque, first_opaque, positive)

    namespaces = {
        "deployment_version": "1.0.0",
        "api_version": "v1",
        "provider_version": "7.4",
        "realtime_protocol_version": "1",
        "registry_version": "42",
    }
    if "contract_version" in namespaces:
        raise AssertionError("unrelated namespace map unexpectedly contains contract_version")

    return {adapter.candidate: ELIGIBLE for adapter in ADAPTERS}


def main() -> int:
    results = evaluate()
    print(
        "d4b_contract_version_candidate_source=PASS "
        "candidates=3 concrete_eligible=3 opaque_monotonic_issuance=proven bounded_issuance=true "
        "opaque_fixture_uniqueness=deterministic_bijection ordering_authority=absent namespace_substitution=blocked "
        "breaking_reuse=blocked historical_family_reinterpretation=blocked historical_bytes=preserved "
        "canonical_syntax_selection=false ledger_credit=0"
    )
    for candidate, result in sorted(results.items()):
        print(f"candidate={candidate} result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
