from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any


class ContractError(ValueError):
    pass


class DuplicateMemberError(ContractError):
    pass


@dataclass(frozen=True)
class Bounds:
    max_depth: int = 8
    max_members: int = 64
    max_array_items: int = 128
    max_string_chars: int = 4096
    max_wire_bytes: int = 65536


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateMemberError(f"duplicate member: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise ContractError(f"non-standard numeric constant rejected: {value}")


def _validate_bounds(value: Any, bounds: Bounds, depth: int = 0) -> None:
    if depth > bounds.max_depth:
        raise ContractError("maximum depth exceeded")
    if isinstance(value, dict):
        if len(value) > bounds.max_members:
            raise ContractError("maximum members exceeded")
        for key, item in value.items():
            if len(key) > bounds.max_string_chars:
                raise ContractError("key length exceeded")
            _validate_bounds(item, bounds, depth + 1)
    elif isinstance(value, list):
        if len(value) > bounds.max_array_items:
            raise ContractError("maximum array items exceeded")
        for item in value:
            _validate_bounds(item, bounds, depth + 1)
    elif isinstance(value, str):
        if len(value) > bounds.max_string_chars:
            raise ContractError("string length exceeded")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ContractError("non-finite number rejected")


def parse_bounded_structured(raw: bytes, bounds: Bounds = Bounds()) -> Any:
    if len(raw) > bounds.max_wire_bytes:
        raise ContractError("wire bound exceeded")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_nonstandard_constant,
        )
    except UnicodeDecodeError as exc:
        raise ContractError("invalid utf-8") from exc
    except json.JSONDecodeError as exc:
        raise ContractError("invalid structured representation") from exc
    _validate_bounds(parsed, bounds)
    return parsed


def canonical_semantic_bytes(value: Any) -> bytes:
    _validate_bounds(value, Bounds(max_depth=64, max_members=65536, max_array_items=65536, max_string_chars=1_000_000, max_wire_bytes=2**31 - 1))
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("value cannot be canonically serialized") from exc


def equivalence_fingerprint(value: Any, *, profile: str) -> str:
    if not isinstance(profile, str) or not profile:
        raise ContractError("comparison profile must be a non-empty string")
    payload = profile.encode("utf-8") + b"\x00" + canonical_semantic_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def _required_string(container: dict[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise ContractError(f"{key} must be a non-empty string")
    return value


def _strict_bool(container: dict[str, Any], key: str, default: bool = False) -> bool:
    if key not in container:
        return default
    value = container[key]
    if not isinstance(value, bool):
        raise ContractError(f"{key} must be boolean")
    return value


def _enum_value_matches_field_type(value: Any, field_type: str, nullable: bool) -> bool:
    if value is None:
        return nullable
    if field_type == "string":
        return isinstance(value, str)
    if field_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and not (
            isinstance(value, float) and not math.isfinite(value)
        )
    if field_type == "boolean":
        return isinstance(value, bool)
    if field_type == "object":
        return isinstance(value, dict)
    if field_type == "array":
        return isinstance(value, list)
    raise ContractError(f"enum-bearing field type is not supported by the reference profile: {field_type}")


def semantic_manifest(contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise ContractError("contract must be an object")
    contract_family = _required_string(contract, "contract_family")
    comparison_profile = _required_string(contract, "comparison_profile")
    historical_reader = _required_string(contract, "historical_reader")
    fields = contract.get("fields")
    if not isinstance(fields, list):
        raise ContractError("fields must be a list")
    normalized = []
    names: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise ContractError("each field must be an object")
        name = field.get("name")
        field_type = field.get("type")
        enum = field.get("enum")
        if not isinstance(name, str) or not name or name in names:
            raise ContractError("field names must be unique non-empty strings")
        if not isinstance(field_type, str) or not field_type:
            raise ContractError(f"field type must be a non-empty string: {name}")
        required = _strict_bool(field, "required")
        nullable = _strict_bool(field, "nullable")
        immutable_for_equivalence = _strict_bool(field, "immutable_for_equivalence")
        if enum is not None:
            if not isinstance(enum, list) or not enum:
                raise ContractError(f"enum must be a non-empty list when present: {name}")
            for item in enum:
                if not _enum_value_matches_field_type(item, field_type, nullable):
                    raise ContractError(f"enum value contradicts declared field type: {name}")
            canonical_enum = [canonical_semantic_bytes(item) for item in enum]
            if len(set(canonical_enum)) != len(canonical_enum):
                raise ContractError(f"enum values must be unique: {name}")
            enum = [item for _, item in sorted(zip(canonical_enum, enum), key=lambda pair: pair[0])]
        names.add(name)
        normalized.append({
            "name": name,
            "type": field_type,
            "required": required,
            "nullable": nullable,
            "enum": enum,
            "immutable_for_equivalence": immutable_for_equivalence,
        })
    return {
        "contract_family": contract_family,
        "fields": sorted(normalized, key=lambda item: item["name"]),
        "comparison_profile": comparison_profile,
        "historical_reader": historical_reader,
    }


def _enum_set(values: list[Any] | None) -> set[bytes] | None:
    if values is None:
        return None
    return {canonical_semantic_bytes(value) for value in values}


def compatibility(old: dict[str, Any], new: dict[str, Any]) -> tuple[bool, list[str]]:
    old_manifest = semantic_manifest(old)
    new_manifest = semantic_manifest(new)
    old_fields = {item["name"]: item for item in old_manifest["fields"]}
    new_fields = {item["name"]: item for item in new_manifest["fields"]}
    reasons: list[str] = []

    if old_manifest["contract_family"] != new_manifest["contract_family"]:
        reasons.append("contract_family_change")

    for name, old_field in old_fields.items():
        new_field = new_fields.get(name)
        if new_field is None:
            reasons.append(f"removed_field:{name}")
            continue
        if new_field["type"] != old_field["type"]:
            reasons.append(f"type_change:{name}")
        if not old_field["required"] and new_field["required"]:
            reasons.append(f"required_tightened:{name}")
        if old_field["nullable"] and not new_field["nullable"]:
            reasons.append(f"nullable_narrowed:{name}")
        old_enum = _enum_set(old_field["enum"])
        new_enum = _enum_set(new_field["enum"])
        if old_enum is None and new_enum is not None:
            reasons.append(f"enum_introduced:{name}")
        elif old_enum is not None and new_enum is not None and not old_enum.issubset(new_enum):
            reasons.append(f"enum_narrowed:{name}")
        if old_field["immutable_for_equivalence"] != new_field["immutable_for_equivalence"]:
            reasons.append(f"equivalence_scope_change:{name}")

    for name, new_field in new_fields.items():
        if name not in old_fields and new_field["required"]:
            reasons.append(f"new_required_field:{name}")

    if old_manifest["comparison_profile"] != new_manifest["comparison_profile"]:
        reasons.append("comparison_profile_change")

    return not reasons, reasons


def require_breaking_change_disposition(old: dict[str, Any], new: dict[str, Any], disposition: str | None) -> None:
    compatible, reasons = compatibility(old, new)
    if compatible:
        return
    if disposition not in {"new_incompatible_contract_version_or_family", "accepted_equality_preserving_migration"}:
        raise ContractError("breaking semantic change lacks governed disposition: " + ",".join(reasons))


def validate_reference_version_token(token: Any) -> None:
    if not isinstance(token, str) or not token or len(token) > 64:
        raise ContractError("reference version token must be a non-empty bounded string")
