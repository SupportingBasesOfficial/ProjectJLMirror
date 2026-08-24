#!/usr/bin/env python3
"""Deterministic contract projections for JLMIRROR Wave 0.

Reviewed Markdown remains normative. This module only projects exact, bounded
pieces of that authority into machine-readable structures for implementation
conformance. It never promotes generated output to normative authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

VERSIONED_ID_RE = re.compile(
    r"(?<![A-Za-z0-9_-])([a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+@[1-9][0-9]*)(?![A-Za-z0-9_-])"
)
SNAKE_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEADING_RE_TEMPLATE = r"^#{1,6}\s+%s\s*$"
FENCED_TEXT_RE = re.compile(r"```(?:text)?\s*\n(.*?)\n```", re.DOTALL)


class ContractProjectionError(ValueError):
    """Raised when normative source cannot be projected without guessing."""


@dataclass(frozen=True)
class ManifestRequirements:
    fields: tuple[str, ...]
    composite_requirements: tuple[str, ...]


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_registry(root: Path) -> dict[str, Any]:
    path = root / "contracts" / "catalog" / "source-registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractProjectionError(f"cannot load {path}: {exc}") from exc

    expected = {
        "schema_version",
        "catalog_id",
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

    sources = data["profile_sources"]
    if not isinstance(sources, list) or not sources or len(sources) != len(set(sources)):
        raise ContractProjectionError("profile_sources must be a non-empty unique list")

    for key in ("http_manifest_source", "event_manifest_source"):
        item = data[key]
        if not isinstance(item, dict) or set(item) != {"path", "heading"}:
            raise ContractProjectionError(f"{key} must contain exactly path + heading")
        if not item["path"] or not item["heading"]:
            raise ContractProjectionError(f"{key} path/heading cannot be blank")

    return data


def _read_source(root: Path, relative: str) -> str:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ContractProjectionError(
            f"source escapes repository root: {relative}"
        ) from exc
    if not path.is_file():
        raise ContractProjectionError(f"registered source missing: {relative}")
    return path.read_text(encoding="utf-8")


def extract_manifest_requirements(
    text: str, heading: str
) -> ManifestRequirements:
    heading_re = re.compile(
        HEADING_RE_TEMPLATE % re.escape(heading), re.MULTILINE
    )
    match = heading_re.search(text)
    if not match:
        raise ContractProjectionError(f"heading not found: {heading}")

    next_heading = re.search(
        r"^#{1,6}\s+.+$", text[match.end() :], re.MULTILINE
    )
    end = match.end() + next_heading.start() if next_heading else len(text)
    section = text[match.end() : end]
    fence = FENCED_TEXT_RE.search(section)
    if not fence:
        raise ContractProjectionError(
            f"no fenced requirement block under heading: {heading}"
        )

    fields: list[str] = []
    composites: list[str] = []
    for raw in fence.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if SNAKE_FIELD_RE.fullmatch(line):
            fields.append(line)
        else:
            composites.append(line)

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


def build_profile_catalog(
    root: Path, registry: dict[str, Any]
) -> dict[str, Any]:
    by_id: dict[str, list[str]] = {}
    for relative in registry["profile_sources"]:
        text = _read_source(root, relative)
        ids = extract_versioned_ids(text)
        if not ids:
            raise ContractProjectionError(
                f"registered profile source yielded no versioned IDs: {relative}"
            )
        for identifier in ids:
            by_id.setdefault(identifier, []).append(relative)

    records = [
        {"id": identifier, "sources": sorted(sources)}
        for identifier, sources in sorted(by_id.items())
    ]
    return {
        "catalog_id": "jlmirror.generated-profile-catalog@1",
        "authority": "projection_only_reviewed_markdown_remains_normative",
        "records": records,
    }


def build_manifest_projection(
    root: Path, source: dict[str, str], projection_id: str
) -> dict[str, Any]:
    text = _read_source(root, source["path"])
    requirements = extract_manifest_requirements(text, source["heading"])
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:jlmirror:{projection_id}",
        "type": "object",
        "required": list(requirements.fields),
        "properties": {name: {} for name in requirements.fields},
        "additionalProperties": True,
        "x-jlmirror-source": source,
        "x-jlmirror-composite-requirements": list(
            requirements.composite_requirements
        ),
        "x-jlmirror-authority": (
            "projection_only_reviewed_markdown_remains_normative"
        ),
    }


def build_bundle(root: Path) -> dict[str, Any]:
    registry = load_registry(root)
    profile_catalog = build_profile_catalog(root, registry)
    http_schema = build_manifest_projection(
        root,
        registry["http_manifest_source"],
        "http-endpoint-manifest:v1",
    )
    event_schema = build_manifest_projection(
        root,
        registry["event_manifest_source"],
        "event-contract-manifest:v1",
    )
    registry_bytes = canonical_json(registry).encode("utf-8")
    return {
        "bundle_id": "jlmirror.contract-projection-bundle@1",
        "authority": "projection_only_reviewed_markdown_remains_normative",
        "source_registry_sha256": sha256(registry_bytes).hexdigest(),
        "profile_catalog": profile_catalog,
        "http_endpoint_manifest_schema": http_schema,
        "event_contract_manifest_schema": event_schema,
    }


def compare_object_schemas(
    previous: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Return structural compatibility; semantic compatibility stays upstream-owned."""

    prev_props = set(previous.get("properties", {}))
    next_props = set(candidate.get("properties", {}))
    prev_required = set(previous.get("required", []))
    next_required = set(candidate.get("required", []))

    removed = sorted(prev_props - next_props)
    added_required = sorted((next_required - prev_required) & next_props)
    added_optional = sorted((next_props - prev_props) - next_required)
    relaxed_required = sorted(prev_required - next_required)

    breaking_reasons: list[str] = []
    if removed:
        breaking_reasons.append("properties_removed")
    if added_required:
        breaking_reasons.append("required_properties_added")

    return {
        "classification": (
            "structurally_breaking"
            if breaking_reasons
            else "structurally_non_breaking"
        ),
        "breaking_reasons": breaking_reasons,
        "removed_properties": removed,
        "added_required_properties": added_required,
        "added_optional_properties": added_optional,
        "relaxed_required_properties": relaxed_required,
        "semantic_compatibility_authority": (
            "Phase 09/10 reviewed contracts own semantic compatibility; "
            "this structural report is insufficient by itself"
        ),
    }
