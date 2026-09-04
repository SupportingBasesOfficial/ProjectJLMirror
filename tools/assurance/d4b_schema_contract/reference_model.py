from __future__ import annotations

import hashlib
import json
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


def parse_bounded_structured(raw: bytes, bounds: Bounds = Bounds()) -> Any:
    if len(raw) > bounds.max_wire_bytes:
        raise ContractError("wire bound exceeded")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except UnicodeDecodeError as exc:
        raise ContractError("invalid utf-8") from exc
    except json.JSONDecodeError as exc:
        raise ContractError("invalid structured representation") from exc
    _validate_bounds(parsed, bounds)
    return parsed


def canonical_semantic_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def equivalence_fingerprint(value: Any, *, profile: str) -> str:
    payload = profile.encode("utf-8") + b"\x00" + canonical_semantic_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def semantic_manifest(contract: dict[str, Any]) -> dict[str, Any]:
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
        if enum is not None:
            if not isinstance(enum, list) or not enum:
                raise ContractError(f"enum must be a non-empty list when present: {name}")
            if len(set(map(repr, enum))) != len(enum):
                raise ContractError(f"enum values must be unique: {name}")
        names.add(name)
        normalized.append({
            "name": name,
            "type": field_type,
            "required": bool(field.get("required", False)),
            "nullable": bool(field.get("nullable", False)),
            "enum": sorted(enum, key=repr) if enum is not None else None,
            "immutable_for_equivalence": bool(field.get("immutable_for_equivalence", False)),
        })
    return {
        "contract_family": contract.get("contract_family"),
        "fields": sorted(normalized, key=lambda item: item["name"]),
        "comparison_profile": contract.get("comparison_profile"),
        "historical_reader": contract.get("historical_reader"),
    }


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
        old_enum = old_field["enum"]
        new_enum = new_field["enum"]
        if old_enum is None and new_enum is not None:
            reasons.append(f"enum_introduced:{name}")
        elif old_enum is not None:
            if new_enum is None:
                pass  # widening is backward-compatible for the reference profile
            elif not set(old_enum).issubset(set(new_enum)):
                reasons.append(f"enum_narrowed:{name}")
        if old_field["immutable_for_equivalence"] != new_field["immutable_for_equivalence"]:
            reasons.append(f"equivalence_scope_change:{name}")

    for name, new_field in new_fields.items():
        if name not in old_fields and new_field["required"]:
            reasons.append(f"new_required_field:{name}")

    if old_manifest["comparison_profile"] != new_manifest["comparison_profile"]:
        reasons.append("comparison_profile_change")
    if not old_manifest["historical_reader"]:
        reasons.append("old_historical_reader_missing")
    if not new_manifest["historical_reader"]:
        reasons.append("new_historical_reader_missing")

    return not reasons, reasons


def require_breaking_change_disposition(old: dict[str, Any], new: dict[str, Any], disposition: str | None) -> None:
    compatible, reasons = compatibility(old, new)
    if compatible:
        return
    if disposition not in {"new_incompatible_contract_version_or_family", "accepted_equality_preserving_migration"}:
        raise ContractError("breaking semantic change lacks governed disposition: " + ",".join(reasons))


def validate_reference_version_token(token: Any) -> None:
    # Reference-only bound. This deliberately does not select the canonical OPEN-EVT-004 syntax.
    if not isinstance(token, str) or not token or len(token) > 64:
        raise ContractError("reference version token must be a non-empty bounded string")
