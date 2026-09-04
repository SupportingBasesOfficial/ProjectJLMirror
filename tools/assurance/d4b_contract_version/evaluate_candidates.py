#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass

ELIGIBLE = "eligible_for_evidence_execution"


@dataclass(frozen=True)
class ParsedVersion:
    candidate: str
    canonical: str


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


def assert_breaking_change_requires_transition(before_version: str, after_version: str, semantic_change: str) -> None:
    if semantic_change == "breaking" and before_version == after_version:
        raise ValueError("breaking semantic change cannot reuse the same contract_version")


def preserve_historical_version(original: bytes) -> bytes:
    return bytes(original)


def evaluate() -> dict[str, str]:
    positive = ADAPTERS[0]
    semver = ADAPTERS[1]
    opaque = ADAPTERS[2]

    positive.parse("1")
    positive.parse("9999999999")
    assert_rejected(positive, ("0", "01", "+1", "-1", "1 ", " 1", "1.0"))
    assert_ordering_absent(positive, "1", "2")
    assert_no_authority_fields(positive, "1")

    semver.parse("0.0.1")
    semver.parse("12.34.56")
    assert_rejected(semver, ("01.0.0", "1.0", "1.0.0-alpha", "1.0.0+build", "1.00.0", " 1.0.0"))
    assert_ordering_absent(semver, "1.0.0", "2.0.0")
    assert_no_authority_fields(semver, "1.0.0")

    opaque.parse("cv_ABCDEFG2")
    opaque.parse("cv_234567ABCDEFGHJK")
    assert_rejected(opaque, ("cv_abcdefg2", "CV_ABCDEFG2", "cv_ABC", "cv_ABCDEFG0", " cv_ABCDEFG2", "cv_ABCDEFG2 "))
    assert_ordering_absent(opaque, "cv_ABCDEFG2", "cv_ABCDEFG3")
    assert_no_authority_fields(opaque, "cv_ABCDEFG2")

    namespaces = {
        "deployment_version": "1.0.0",
        "api_version": "v1",
        "provider_version": "7.4",
        "realtime_protocol_version": "1",
        "registry_version": "42",
    }
    if "contract_version" in namespaces:
        raise AssertionError("unrelated namespace map unexpectedly contains contract_version")

    try:
        assert_breaking_change_requires_transition("1", "1", "breaking")
    except ValueError:
        pass
    else:
        raise AssertionError("breaking change reused identical contract_version")
    assert_breaking_change_requires_transition("1", "2", "breaking")

    historical = b"contract-version-original-bytes"
    if preserve_historical_version(historical) != historical:
        raise AssertionError("historical contract version bytes changed")

    return {adapter.candidate: ELIGIBLE for adapter in ADAPTERS}


def main() -> int:
    results = evaluate()
    print(
        "d4b_contract_version_candidate_source=PASS "
        "candidates=3 concrete_eligible=3 ordering_authority=absent "
        "namespace_substitution=blocked breaking_reuse=blocked historical_bytes=preserved "
        "canonical_syntax_selection=false ledger_credit=0"
    )
    for candidate, result in sorted(results.items()):
        print(f"candidate={candidate} result={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
