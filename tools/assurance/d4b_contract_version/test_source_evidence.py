#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "assurance" / "d4b_contract_version"))
import evaluate_candidates as evaluator
import validate_source_evidence as validator


def snapshot() -> dict[Path, object]:
    paths = (validator.MANIFEST, validator.PLAN, validator.LEDGER, validator.STATE)
    return {path: json.loads((ROOT / path).read_text(encoding="utf-8")) for path in paths}


def mutate_and_validate(mutator) -> list[str]:
    data = snapshot()
    mutator(data)
    with TemporaryDirectory() as td:
        root = Path(td)
        for path, value in data.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                target.write_bytes(value)
            else:
                target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return validator.validate(root)


def obj(data: dict[Path, object], path: Path) -> dict:
    value = data[path]
    assert isinstance(value, dict)
    return value


def must_fail(mutator, fragment: str) -> None:
    errors = mutate_and_validate(mutator)
    if not any(fragment in error for error in errors):
        raise AssertionError(f"expected {fragment!r}, got {errors!r}")


def inject_duplicate_selection(data: dict[Path, object]) -> None:
    raw = (ROOT / validator.MANIFEST).read_bytes()
    needle = b'  "selection_state": "not_selected",\n'
    if raw.count(needle) != 1:
        raise AssertionError("selection_state line not unique")
    data[validator.MANIFEST] = raw.replace(needle, b'  "selection_state": "selected",\n' + needle, 1)


def assert_monotonic_issuer_rejects_regression() -> None:
    adapter = evaluator.OpaqueMonotonicToken()
    issuer = evaluator.OpaqueMonotonicIssuer()
    first = issuer.issue(10)
    second = issuer.issue(11)
    adapter.parse(first)
    adapter.parse(second)
    if first == second:
        raise AssertionError("opaque monotonic issuer duplicated token")
    for sequence in (11, 10, 9, 0, -1, evaluator.MAX_ISSUANCE_SEQUENCE + 1):
        try:
            issuer.issue(sequence)
        except ValueError:
            continue
        raise AssertionError(f"issuer accepted invalid sequence {sequence}")
    evaluator.assert_ordering_absent(adapter, first, second)


def assert_historical_cross_family_reinterpretation_blocked() -> None:
    integer = evaluator.PositiveIntegerRevision()
    semver = evaluator.SemanticVersionLike()
    evidence = integer.retain_historical("1")
    restored = integer.restore_historical(evidence)
    if restored.canonical != "1" or evidence.original_bytes != b"1":
        raise AssertionError("historical integer evidence changed")
    try:
        semver.restore_historical(evidence)
    except ValueError as exc:
        if "candidate family mismatch" not in str(exc):
            raise
    else:
        raise AssertionError("cross-family historical reinterpretation was accepted")


def main() -> int:
    results = evaluator.evaluate()
    if results != validator.EXPECTED_RESULTS:
        raise AssertionError(f"candidate evaluator mismatch: {results!r}")
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical source evidence invalid: {errors!r}")

    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("candidate", "positive_integer_family_revision"), "source manifest exact key schema drift")
    must_fail(inject_duplicate_selection, "duplicate JSON member 'selection_state'")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("canonical_contract_version_syntax_selected", True), "must not select canonical syntax")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("selection_state", "selected"), "must not select D4-B")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("selection_authority", "granted"), "selection authority escalation")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("current_run_auto_credit", True), "must not auto-credit ledger")
    must_fail(lambda d: obj(d, validator.MANIFEST)["ledger_credit"].append("contract_version_representation_and_breaking_change_vectors"), "must not auto-credit ledger")
    must_fail(lambda d: obj(d, validator.MANIFEST)["candidate_results"].__setitem__("positive_integer_family_revision", "selected"), "concrete candidate result inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST).__setitem__("equivalent_reviewed_representation", "eligible_for_evidence_execution"), "equivalent candidate class must remain unevaluated")
    must_fail(lambda d: obj(d, validator.MANIFEST)["required_proofs"].pop(), "required proof inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("opaque_monotonic_candidate_requires_strictly_increasing_internal_issuance_sequence_while_external_tokens_remain_opaque"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.MANIFEST)["source_assertions"].remove("historical_candidate_family_and_original_version_bytes_are_preserved_and_cross_family_reinterpretation_fails_closed"), "source assertion inventory drift")
    must_fail(lambda d: obj(d, validator.LEDGER).__setitem__("candidate", "positive_integer_family_revision"), "D4-B ledger selection drift")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("gate_state", "accepted"), "D4 gate escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("canonical_product_implementation_authority", "granted"), "Product authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("wave4_implementation_authority", "granted"), "Wave4 authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("production_authority", "granted"), "production authority escalation")
    must_fail(lambda d: obj(d, validator.STATE).__setitem__("c3_numeric_topology_authority", "selected"), "C3 authority escalation")

    for adapter in evaluator.ADAPTERS:
        valid = {
            "positive_integer_family_revision": ("1", "2"),
            "semantic_version_like_contract_revision": ("1.0.0", "2.0.0"),
            "opaque_monotonic_contract_token": ("cv_ABCDEFG2", "cv_ABCDEFG3"),
        }[adapter.candidate]
        evaluator.assert_ordering_absent(adapter, *valid)
        evaluator.assert_no_authority_fields(adapter, valid[0])

    assert_monotonic_issuer_rejects_regression()
    assert_historical_cross_family_reinterpretation_blocked()

    print("d4b_contract_version_source_falsification=PASS duplicate_json=blocked hidden_selection=blocked syntax_selection=blocked auto_credit=blocked candidate_promotion=blocked proof_weakening=blocked opaque_monotonic_regression=blocked opaque_issuance_overflow=blocked historical_cross_family_reinterpretation=blocked ordering_authority=blocked authority_fields=blocked ledger_selection=blocked d4_authority_escalation=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
