#!/usr/bin/env python3
"""Deterministic contract projections for JLMIRROR Wave 0.

Reviewed Markdown remains normative. This module only projects exact, pinned,
bounded pieces of that authority into machine-readable structures for
implementation conformance. Generated output never becomes normative authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
from typing import Any

VERSIONED_ID_RE = re.compile(
    r"(?<![A-Za-z0-9_-])([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+@[1-9][0-9]*)(?![A-Za-z0-9_-])"
)
SNAKE_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEADING_RE_TEMPLATE = r"^#{1,6}\s+%s\s*$"
FENCED_TEXT_RE = re.compile(r"```(?:text)?\s*\n(.*?)\n```", re.DOTALL)


class ContractProjectionError(ValueError):
    """Raised when normative source cannot be projected without guessing."""


@dataclass(frozen=True)
class CompositeRequirement:
    source_text: str
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class ManifestRequirements:
    fields: tuple[str, ...]
    composite_requirements: tuple[CompositeRequirement, ...]


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def git_blob_sha(data: bytes) -> str:
    payload = f"blob {len(data)}\0".encode("ascii") + data
    return sha1(payload).hexdigest()


def _validate_pinned_source_shape(item: Any, label: str) -> None:
    if not isinstance(item, dict) or set(item) != {"path", "git_blob_sha"}:
        raise ContractProjectionError(
            f"{label} must contain exactly path + git_blob_sha"
        )
    if not isinstance(item["path"], str) or not item["path"].startswith("docs/"):
        raise ContractProjectionError(f"{label} path must be a docs/ Markdown path")
    if not isinstance(item["git_blob_sha"], str) or not HEX40_RE.fullmatch(
        item["git_blob_sha"]
    ):
        raise ContractProjectionError(f"{label} git_blob_sha must be 40 lowercase hex")


def _validate_manifest_source_shape(item: Any, label: str) -> None:
    expected = {"path", "git_blob_sha", "heading", "composite_requirements"}
    if not isinstance(item, dict) or set(item) != expected:
        raise ContractProjectionError(
            f"{label} must contain exactly {sorted(expected)}"
        )
    _validate_pinned_source_shape(
        {"path": item["path"], "git_blob_sha": item["git_blob_sha"]}, label
    )
    if not isinstance(item["heading"], str) or not item["heading"]:
        raise ContractProjectionError(f"{label} heading cannot be blank")
    composites = item["composite_requirements"]
    if not isinstance(composites, list):
        raise ContractProjectionError(f"{label} composite_requirements must be a list")
    seen_source_text: set[str] = set()
    for index, composite in enumerate(composites):
        if not isinstance(composite, dict) or set(composite) != {
            "source_text",
            "alternatives",
        }:
            raise ContractProjectionError(
                f"{label} composite requirement {index} must contain source_text + alternatives"
            )
        source_text = composite["source_text"]
        alternatives = composite["alternatives"]
        if not isinstance(source_text, str) or not source_text:
            raise ContractProjectionError(
                f"{label} composite requirement {index} source_text cannot be blank"
            )
        if source_text in seen_source_text:
            raise ContractProjectionError(
                f"{label} duplicate composite source_text: {source_text}"
            )
        seen_source_text.add(source_text)
        if (
            not isinstance(alternatives, list)
            or len(alternatives) < 2
            or len(alternatives) != len(set(alternatives))
            or any(
                not isinstance(name, str) or not SNAKE_FIELD_RE.fullmatch(name)
                for name in alternatives
            )
        ):
            raise ContractProjectionError(
                f"{label} composite alternatives must be >=2 unique snake_case names"
            )


def load_registry(root: Path) -> dict[str, Any]:
    path = root / "contracts" / "catalog" / "source-registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractProjectionError(f"cannot load {path}: {exc}") from exc

    expected = {
        "schema_version",
        "catalog_id",
        "accepted_authority_base",
        "profile_sources",
        "http_manifest_source",
        "event_manifest_source",
    }
    if set(data) != expected:
        raise ContractProjectionError(
            f"source registry keys must be exactly {sorted(expected)}"
        )
    if (
        data["schema_version"] != 1
        or data["catalog_id"] != "jlmirror.contract-source-registry@1"
    ):
        raise ContractProjectionError("unsupported source registry identity/version")
    if not isinstance(data["accepted_authority_base"], str) or not HEX40_RE.fullmatch(
        data["accepted_authority_base"]
    ):
        raise ContractProjectionError("accepted_authority_base must be 40 lowercase hex")

    sources = data["profile_sources"]
    if not isinstance(sources, list) or not sources:
        raise ContractProjectionError("profile_sources must be a non-empty list")
    paths: list[str] = []
    for index, source in enumerate(sources):
        _validate_pinned_source_shape(source, f"profile_sources[{index}]")
        paths.append(source["path"])
    if len(paths) != len(set(paths)):
        raise ContractProjectionError("profile source paths must be unique")

    _validate_manifest_source_shape(data["http_manifest_source"], "http_manifest_source")
    _validate_manifest_source_shape(data["event_manifest_source"], "event_manifest_source")
    return data


def validate_registry_schema_contract(root: Path) -> list[str]:
    findings: list[str] = []
    schema_path = root / "contracts" / "catalog" / "source-registry.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load source registry schema: {exc}"]

    expected_required = {
        "schema_version",
        "catalog_id",
        "accepted_authority_base",
        "profile_sources",
        "http_manifest_source",
        "event_manifest_source",
    }
    if schema.get("$id") != "urn:jlmirror:contracts:source-registry:v1":
        findings.append("source registry schema $id drift")
    if set(schema.get("required", [])) != expected_required:
        findings.append("source registry schema required-key set drift")
    props = schema.get("properties", {})
    if props.get("schema_version", {}).get("const") != 1:
        findings.append("source registry schema version const drift")
    if props.get("catalog_id", {}).get("const") != "jlmirror.contract-source-registry@1":
        findings.append("source registry schema catalog_id const drift")
    if schema.get("additionalProperties") is not False:
        findings.append("source registry schema must reject unknown top-level properties")

    if props.get("accepted_authority_base") != {
        "type": "string",
        "pattern": "^[0-9a-f]{40}$",
    }:
        findings.append("source registry schema accepted_authority_base contract drift")
    profile_sources = props.get("profile_sources", {})
    if (
        profile_sources.get("minItems") != 1
        or profile_sources.get("uniqueItems") is not True
        or profile_sources.get("items") != {"$ref": "#/$defs/pinned_source"}
    ):
        findings.append("source registry schema profile_sources contract drift")

    defs = schema.get("$defs", {})
    pinned = defs.get("pinned_source", {})
    if (
        pinned.get("additionalProperties") is not False
        or set(pinned.get("required", [])) != {"path", "git_blob_sha"}
        or pinned.get("properties", {}).get("path")
        != {"type": "string", "pattern": "^docs/.+\\.md$"}
        or pinned.get("properties", {}).get("git_blob_sha")
        != {"type": "string", "pattern": "^[0-9a-f]{40}$"}
    ):
        findings.append("source registry schema pinned_source contract drift")

    manifest = defs.get("manifest_source", {})
    if (
        manifest.get("additionalProperties") is not False
        or set(manifest.get("required", []))
        != {"path", "git_blob_sha", "heading", "composite_requirements"}
        or manifest.get("properties", {}).get("path")
        != {"type": "string", "pattern": "^docs/.+\\.md$"}
        or manifest.get("properties", {}).get("git_blob_sha")
        != {"type": "string", "pattern": "^[0-9a-f]{40}$"}
        or manifest.get("properties", {}).get("heading")
        != {"type": "string", "minLength": 1}
        or manifest.get("properties", {}).get("composite_requirements")
        != {"type": "array", "items": {"$ref": "#/$defs/composite_requirement"}}
    ):
        findings.append("source registry schema manifest_source contract drift")

    composite = defs.get("composite_requirement", {})
    alternatives = composite.get("properties", {}).get("alternatives", {})
    if (
        composite.get("additionalProperties") is not False
        or set(composite.get("required", [])) != {"source_text", "alternatives"}
        or composite.get("properties", {}).get("source_text")
        != {"type": "string", "minLength": 1}
        or alternatives.get("type") != "array"
        or alternatives.get("minItems") != 2
        or alternatives.get("uniqueItems") is not True
        or alternatives.get("items")
        != {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}
    ):
        findings.append("source registry schema composite_requirement contract drift")
    return findings


def _read_pinned_source(root: Path, source: dict[str, Any]) -> str:
    relative = source["path"]
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ContractProjectionError(
            f"source escapes repository root: {relative}"
        ) from exc
    if not path.is_file():
        raise ContractProjectionError(f"registered source missing: {relative}")
    data = path.read_bytes()
    actual_blob = git_blob_sha(data)
    if actual_blob != source["git_blob_sha"]:
        raise ContractProjectionError(
            f"registered normative source drift: {relative}; expected blob "
            f"{source['git_blob_sha']}, actual {actual_blob}. Update requires explicit governance handoff."
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractProjectionError(f"registered source is not UTF-8: {relative}") from exc


def extract_manifest_requirements(
    text: str,
    heading: str,
    composite_specs: tuple[CompositeRequirement, ...] = (),
) -> ManifestRequirements:
    heading_re = re.compile(
        HEADING_RE_TEMPLATE % re.escape(heading), re.MULTILINE
    )
    match = heading_re.search(text)
    if not match:
        raise ContractProjectionError(f"heading not found: {heading}")

    next_heading = re.search(r"^#{1,6}\s+.+$", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    section = text[match.end() : end]
    fence = FENCED_TEXT_RE.search(section)
    if not fence:
        raise ContractProjectionError(
            f"no fenced requirement block under heading: {heading}"
        )

    allowed_composites = {item.source_text: item for item in composite_specs}
    fields: list[str] = []
    composites: list[CompositeRequirement] = []
    seen_composites: set[str] = set()

    for raw in fence.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if SNAKE_FIELD_RE.fullmatch(line):
            fields.append(line)
            continue
        composite = allowed_composites.get(line)
        if composite is None:
            raise ContractProjectionError(
                f"unexpected non-machine manifest requirement under {heading}: {line!r}"
            )
        if line in seen_composites:
            raise ContractProjectionError(
                f"duplicate composite manifest requirement under {heading}: {line!r}"
            )
        seen_composites.add(line)
        composites.append(composite)

    missing_composites = sorted(set(allowed_composites) - seen_composites)
    if missing_composites:
        raise ContractProjectionError(
            f"registered composite requirement(s) not present under {heading}: {missing_composites}"
        )
    if not fields:
        raise ContractProjectionError(
            f"no machine field names found under heading: {heading}"
        )
    if len(fields) != len(set(fields)):
        raise ContractProjectionError(
            f"duplicate manifest field under heading: {heading}"
        )
    return ManifestRequirements(tuple(fields), tuple(composites))


def extract_versioned_ids(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(VERSIONED_ID_RE.findall(text))))


def _composite_specs(source: dict[str, Any]) -> tuple[CompositeRequirement, ...]:
    return tuple(
        CompositeRequirement(
            source_text=item["source_text"], alternatives=tuple(item["alternatives"])
        )
        for item in source["composite_requirements"]
    )


def build_profile_catalog(root: Path, registry: dict[str, Any]) -> dict[str, Any]:
    by_id: dict[str, list[str]] = {}
    for source in registry["profile_sources"]:
        text = _read_pinned_source(root, source)
        ids = extract_versioned_ids(text)
        if not ids:
            raise ContractProjectionError(
                f"registered profile source yielded no versioned IDs: {source['path']}"
            )
        for identifier in ids:
            by_id.setdefault(identifier, []).append(source["path"])

    records = [
        {"id": identifier, "source_documents": sorted(sources)}
        for identifier, sources in sorted(by_id.items())
    ]
    return {
        "catalog_id": "jlmirror.generated-profile-catalog@1",
        "accepted_authority_base": registry["accepted_authority_base"],
        "authority": "projection_only_reviewed_markdown_remains_normative",
        "records": records,
    }


def build_manifest_projection(
    root: Path, source: dict[str, Any], projection_id: str
) -> dict[str, Any]:
    text = _read_pinned_source(root, source)
    requirements = extract_manifest_requirements(
        text, source["heading"], _composite_specs(source)
    )
    properties = {name: {} for name in requirements.fields}
    all_of: list[dict[str, Any]] = []
    composite_records: list[dict[str, Any]] = []
    for composite in requirements.composite_requirements:
        for alternative in composite.alternatives:
            properties.setdefault(alternative, {})
        all_of.append(
            {
                "anyOf": [
                    {"required": [alternative]}
                    for alternative in composite.alternatives
                ],
                "x-jlmirror-source-requirement": composite.source_text,
            }
        )
        composite_records.append(
            {
                "source_text": composite.source_text,
                "alternatives": list(composite.alternatives),
            }
        )

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:jlmirror:{projection_id}",
        "type": "object",
        "required": list(requirements.fields),
        "properties": properties,
        "allOf": all_of,
        "additionalProperties": True,
        "x-jlmirror-source": {
            "path": source["path"],
            "git_blob_sha": source["git_blob_sha"],
            "heading": source["heading"],
        },
        "x-jlmirror-composite-requirements": composite_records,
        "x-jlmirror-authority": "projection_only_reviewed_markdown_remains_normative",
    }


def build_bundle(root: Path) -> dict[str, Any]:
    registry = load_registry(root)
    profile_catalog = build_profile_catalog(root, registry)
    http_schema = build_manifest_projection(
        root, registry["http_manifest_source"], "http-endpoint-manifest:v1"
    )
    event_schema = build_manifest_projection(
        root, registry["event_manifest_source"], "event-contract-manifest:v1"
    )
    registry_bytes = canonical_json(registry).encode("utf-8")
    return {
        "bundle_id": "jlmirror.contract-projection-bundle@1",
        "accepted_authority_base": registry["accepted_authority_base"],
        "authority": "projection_only_reviewed_markdown_remains_normative",
        "source_registry_sha256": sha256(registry_bytes).hexdigest(),
        "profile_catalog": profile_catalog,
        "http_endpoint_manifest_schema": http_schema,
        "event_contract_manifest_schema": event_schema,
    }


def compare_object_schemas(
    previous: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Report structural change without claiming semantic compatibility."""

    prev_prop_defs = previous.get("properties", {})
    next_prop_defs = candidate.get("properties", {})
    prev_props = set(prev_prop_defs)
    next_props = set(next_prop_defs)
    prev_required = set(previous.get("required", []))
    next_required = set(candidate.get("required", []))

    removed = sorted(prev_props - next_props)
    added_required = sorted((next_required - prev_required) & next_props)
    added_optional = sorted((next_props - prev_props) - next_required)
    relaxed_required = sorted(prev_required - next_required)
    changed_properties = sorted(
        name
        for name in (prev_props & next_props)
        if canonical_json(prev_prop_defs[name]) != canonical_json(next_prop_defs[name])
    )
    composite_changed = canonical_json(previous.get("allOf", [])) != canonical_json(
        candidate.get("allOf", [])
    )
    object_envelope_changed = any(
        canonical_json(previous.get(keyword)) != canonical_json(candidate.get(keyword))
        for keyword in ("type", "additionalProperties")
    )

    review_reasons: list[str] = []
    if removed:
        review_reasons.append("properties_removed")
    if added_required:
        review_reasons.append("required_properties_added")
    if relaxed_required:
        review_reasons.append("required_properties_relaxed")
    if changed_properties:
        review_reasons.append("property_definitions_changed")
    if composite_changed:
        review_reasons.append("composite_requirements_changed")
    if object_envelope_changed:
        review_reasons.append("object_envelope_changed")

    if review_reasons:
        classification = "structural_change_requires_review"
    elif added_optional:
        classification = "structurally_additive_candidate"
    else:
        classification = "structurally_identical"

    return {
        "classification": classification,
        "review_reasons": review_reasons,
        "removed_properties": removed,
        "added_required_properties": added_required,
        "added_optional_properties": added_optional,
        "relaxed_required_properties": relaxed_required,
        "changed_property_definitions": changed_properties,
        "composite_requirements_changed": composite_changed,
        "object_envelope_changed": object_envelope_changed,
        "semantic_compatibility_authority": (
            "Phase 09/10 reviewed contracts own semantic compatibility; "
            "this structural report cannot approve compatibility"
        ),
    }
