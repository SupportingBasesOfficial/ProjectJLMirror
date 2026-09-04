from __future__ import annotations

import copy

from reference_model import (
    Bounds,
    ContractError,
    DuplicateMemberError,
    canonical_semantic_bytes,
    compatibility,
    equivalence_fingerprint,
    parse_bounded_structured,
    require_breaking_change_disposition,
    semantic_manifest,
    validate_reference_version_token,
)


def expect_failure(fn, exc_type=Exception):
    try:
        fn()
    except exc_type:
        return
    raise AssertionError(f"expected {exc_type.__name__}")


BASE = {
    "contract_family": "inventory.item.changed",
    "comparison_profile": "immutable-content-v1",
    "historical_reader": "reader-v1-retained",
    "fields": [
        {"name": "tenant_id", "type": "string", "required": True, "nullable": False, "immutable_for_equivalence": True},
        {"name": "message_id", "type": "string", "required": True, "nullable": False, "immutable_for_equivalence": True},
        {"name": "status", "type": "string", "required": True, "nullable": False, "enum": ["active", "inactive"], "immutable_for_equivalence": True},
        {"name": "note", "type": "string", "required": False, "nullable": True, "immutable_for_equivalence": False},
    ],
}


def main() -> int:
    parsed = parse_bounded_structured(b'{"b":2,"a":1}')
    assert canonical_semantic_bytes(parsed) == b'{"a":1,"b":2}'
    assert equivalence_fingerprint(parsed, profile="p1") == equivalence_fingerprint({"a": 1, "b": 2}, profile="p1")
    assert equivalence_fingerprint(parsed, profile="p1") != equivalence_fingerprint(parsed, profile="p2")

    expect_failure(lambda: parse_bounded_structured(b'{"tenant_id":"a","tenant_id":"b"}'), DuplicateMemberError)
    expect_failure(lambda: parse_bounded_structured(b'"abcdef"', Bounds(max_string_chars=3)), ContractError)
    expect_failure(lambda: parse_bounded_structured(b'[[[1]]]', Bounds(max_depth=2)), ContractError)
    expect_failure(lambda: parse_bounded_structured(b'[1,2,3]', Bounds(max_array_items=2)), ContractError)
    expect_failure(lambda: parse_bounded_structured(b'{"a":1,"b":2}', Bounds(max_members=1)), ContractError)

    manifest_a = semantic_manifest(BASE)
    reordered = copy.deepcopy(BASE)
    reordered["fields"] = list(reversed(reordered["fields"]))
    assert semantic_manifest(reordered) == manifest_a

    additive = copy.deepcopy(BASE)
    additive["fields"].append({"name": "optional_new", "type": "string", "required": False, "nullable": True})
    compatible, reasons = compatibility(BASE, additive)
    assert compatible and reasons == []

    breaking_cases: list[dict] = []
    removed = copy.deepcopy(BASE); removed["fields"] = [f for f in removed["fields"] if f["name"] != "status"]; breaking_cases.append(removed)
    changed_type = copy.deepcopy(BASE); next(f for f in changed_type["fields"] if f["name"] == "status")["type"] = "integer"; breaking_cases.append(changed_type)
    required_add = copy.deepcopy(BASE); required_add["fields"].append({"name": "must", "type": "string", "required": True}); breaking_cases.append(required_add)
    optional_to_required = copy.deepcopy(BASE); next(f for f in optional_to_required["fields"] if f["name"] == "note")["required"] = True; breaking_cases.append(optional_to_required)
    nullable_narrow = copy.deepcopy(BASE); next(f for f in nullable_narrow["fields"] if f["name"] == "note")["nullable"] = False; breaking_cases.append(nullable_narrow)
    enum_narrow = copy.deepcopy(BASE); next(f for f in enum_narrow["fields"] if f["name"] == "status")["enum"] = ["active"]; breaking_cases.append(enum_narrow)
    enum_introduced = copy.deepcopy(BASE); next(f for f in enum_introduced["fields"] if f["name"] == "note")["enum"] = ["operator", "system"]; breaking_cases.append(enum_introduced)
    eq_scope = copy.deepcopy(BASE); next(f for f in eq_scope["fields"] if f["name"] == "note")["immutable_for_equivalence"] = True; breaking_cases.append(eq_scope)
    comparison = copy.deepcopy(BASE); comparison["comparison_profile"] = "immutable-content-v2"; breaking_cases.append(comparison)
    family = copy.deepcopy(BASE); family["contract_family"] = "inventory.item.updated"; breaking_cases.append(family)
    new_reader_missing = copy.deepcopy(BASE); new_reader_missing["historical_reader"] = None; breaking_cases.append(new_reader_missing)

    for changed in breaking_cases:
        compatible, reasons = compatibility(BASE, changed)
        assert not compatible and reasons
        expect_failure(lambda changed=changed: require_breaking_change_disposition(BASE, changed, None), ContractError)
        require_breaking_change_disposition(BASE, changed, "new_incompatible_contract_version_or_family")

    no_reader = copy.deepcopy(BASE); no_reader["historical_reader"] = None
    compatible, reasons = compatibility(no_reader, additive)
    assert not compatible and "old_historical_reader_missing" in reasons

    malformed_field = copy.deepcopy(BASE); malformed_field["fields"].append({"name": "broken", "type": None})
    expect_failure(lambda: semantic_manifest(malformed_field), ContractError)
    duplicate_enum = copy.deepcopy(BASE); next(f for f in duplicate_enum["fields"] if f["name"] == "status")["enum"] = ["active", "active"]
    expect_failure(lambda: semantic_manifest(duplicate_enum), ContractError)

    validate_reference_version_token("v-reference-1")
    expect_failure(lambda: validate_reference_version_token(""), ContractError)
    expect_failure(lambda: validate_reference_version_token(1), ContractError)
    expect_failure(lambda: validate_reference_version_token("x" * 65), ContractError)

    print(
        "d4b_schema_contract=PASS canonical_semantics=deterministic duplicates=blocked bounds=blocked "
        "semantic_manifest=stable compatibility=semantic_narrowing_closed historical_reader=required equivalence_profile=versioned "
        "breaking_changes=governed version_syntax=reference_only_not_selected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
