#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_CORE_PATH = Path(__file__).resolve().with_name("g2_scope_core.py")
REPOSITORY_CORE_PATH = ROOT / "tools/assurance/g2_scope_core.py"
CORE_PATH = LOCAL_CORE_PATH if LOCAL_CORE_PATH.is_file() else REPOSITORY_CORE_PATH
spec = importlib.util.spec_from_file_location("jlmirror_g2_scope_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load canonical G2 scope core")
_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_core)
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

DEFAULT_ROOT = Path.cwd()
EXPECTED_READINESS_VALIDATOR = "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py"
_ORIGINAL_VALIDATE_SEMANTIC_ARTIFACT = _core.validate_semantic_artifact
_DDL_MODIFIERS = "temp|temporary|unlogged|unique|concurrently"


def _component_sequence_hit(identifier: str, marker: str) -> bool:
    parts = _core._split_components(identifier)
    marker_parts = _core._split_components(marker)
    if not parts or not marker_parts:
        return False
    for start in range(len(parts) - len(marker_parts) + 1):
        matched = True
        for offset, marker_part in enumerate(marker_parts):
            part = parts[start + offset]
            if part not in _core._identifier_variants(marker_part):
                matched = False
                break
        if not matched:
            continue
        if marker_parts == ["automation"] and start > 0 and parts[start - 1] == "browser":
            continue
        return True
    return False


def _hardened_marker_errors(path: str, decoded: str, policy: dict) -> list[str]:
    errors: list[str] = []
    scan_text = re.sub(r"\bbrowser[\s_-]+automation\b", "browser_e2e", decoded, flags=re.IGNORECASE)
    identifiers = _core._raw_identifiers(scan_text)
    for marker in policy.get("forbidden_code_markers", []):
        if marker in _core.STRUCTURAL_MARKERS:
            continue
        if any(_component_sequence_hit(identifier, marker) for identifier in identifiers):
            errors.append(f"forbidden G2 semantic code marker '{marker}' in {path}")
    return errors


def _persistence_aliases(decoded: str) -> set[str]:
    aliases = set(_core.PERSISTENCE_RECEIVERS)
    changed = True
    while changed:
        changed = False
        receiver = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
        patterns = (
            rf"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:\(\s*)?(?:{receiver})(?:\s*\))?\s*[;\n]",
            rf"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:{receiver})\s*(?:\?\.|\.)\s*[A-Za-z_$][A-Za-z0-9_$]*",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
                alias = match.group(1)
                if alias not in aliases:
                    aliases.add(alias)
                    changed = True
    return aliases


def _static_computed_member(expr: str) -> str | None:
    pieces = re.split(r"\s*\+\s*", expr.strip())
    values: list[str] = []
    for piece in pieces:
        match = re.fullmatch(r"['\"]([^'\"]*)['\"]", piece.strip())
        if not match:
            return None
        values.append(match.group(1))
    return "".join(values).casefold()


def _has_hardened_persistence_write(decoded: str) -> bool:
    aliases = _persistence_aliases(decoded)
    receiver = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    write = "|".join(re.escape(name) for name in sorted(_core.PERSISTENCE_WRITES, key=len, reverse=True))
    receiver_expr = rf"(?:\(\s*)?(?:{receiver})(?:\s*\))?"
    direct_patterns = (
        rf"\b{receiver_expr}\s*(?:\?\.|\.)\s*(?:{write})\s*(?:\(|\.\s*(?:call|apply)\s*\()",
        rf"\b(?:const|let|var)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*{receiver_expr}\s*(?:\?\.|\.)\s*(?:{write})\b",
        rf"\b(?:const|let|var)\s*\{{[^}}]*\b(?:{write})\b[^}}]*\}}\s*=\s*{receiver_expr}\b",
    )
    if any(re.search(pattern, decoded, flags=re.IGNORECASE) for pattern in direct_patterns):
        return True
    for match in re.finditer(rf"\b{receiver_expr}\s*(?:\?\.)?\s*\[([^\]]+)\]\s*\(", decoded, flags=re.IGNORECASE):
        member = _static_computed_member(match.group(1))
        if member in _core.PERSISTENCE_WRITES:
            return True
    method_aliases: set[str] = set()
    for match in re.finditer(rf"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*{receiver_expr}\s*(?:\?\.|\.)\s*({write})\b", decoded, flags=re.IGNORECASE):
        method_aliases.add(match.group(1))
    return any(re.search(rf"\b{re.escape(alias)}\s*\(", decoded) for alias in method_aliases)


def _raw_secret_identifier(identifier: str) -> bool:
    parts = set(_core._split_components(identifier))
    if "credential" in parts and "binding" in parts and ("ref" in parts or "reference" in parts):
        return False
    return bool(parts & _core.SECRET_TERMS)


def _contains_secret_reference(text: str, tainted: set[str]) -> bool:
    for identifier in _core._raw_identifiers(text):
        if identifier in tainted or _raw_secret_identifier(identifier):
            return True
    return False


def _secret_taint(decoded: str) -> set[str]:
    tainted = {identifier for identifier in _core._raw_identifiers(decoded) if _raw_secret_identifier(identifier)}
    changed = True
    while changed:
        changed = False
        for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*([^;\n]+)", decoded):
            target, expression = match.group(1), match.group(2)
            if target not in tainted and _contains_secret_reference(expression, tainted):
                tainted.add(target)
                changed = True
    return tainted


def _sink_call_contains(text: str, names: set[str]) -> bool:
    sink = "|".join(sorted(_core.SECRET_SINK_TERMS, key=len, reverse=True))
    for match in re.finditer(rf"(?:\b[A-Za-z_$][A-Za-z0-9_$]*\s*\.)?\b(?:{sink})\s*\((.*?)\)", text, flags=re.IGNORECASE | re.DOTALL):
        if _contains_secret_reference(match.group(1), names):
            return True
    if re.search(r"\breturn\s+\{", text) and _contains_secret_reference(text, names):
        return True
    return False


def _sink_wrappers(decoded: str) -> set[str]:
    wrappers: set[str] = set()
    functions = list(re.finditer(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{(.*?)\}", decoded, flags=re.DOTALL))
    arrows = list(re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(([^)]*)\)\s*=>\s*(\{.*?\}|[^;\n]+)", decoded, flags=re.DOTALL))
    definitions = [(m.group(1), m.group(2), m.group(3)) for m in functions + arrows]
    changed = True
    while changed:
        changed = False
        for name, params_text, body in definitions:
            params = {p.strip() for p in params_text.split(",") if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", p.strip())}
            if not params or name in wrappers:
                continue
            direct = _sink_call_contains(body, params)
            indirect = any(re.search(rf"\b{re.escape(wrapper)}\s*\((.*?)\)", body, flags=re.DOTALL) and _contains_secret_reference(body, params) for wrapper in wrappers)
            if direct or indirect:
                wrappers.add(name)
                changed = True
    return wrappers


def _has_hardened_secret_flow(decoded: str) -> bool:
    tainted = _secret_taint(decoded)
    if not tainted:
        return False
    if _sink_call_contains(decoded, tainted):
        return True
    for wrapper in _sink_wrappers(decoded):
        for match in re.finditer(rf"\b{re.escape(wrapper)}\s*\((.*?)\)", decoded, flags=re.DOTALL):
            if _contains_secret_reference(match.group(1), tainted):
                return True
    return False


def _has_hardened_ddl(decoded: str) -> bool:
    uncommented = _core._strip_comments(decoded.casefold())
    pre_modifiers = rf"(?:\s+(?:{_DDL_MODIFIERS}))*"
    create = rf"\bcreate(?:\s+or\s+replace)?{pre_modifiers}\s+(?:{_core.DDL_OBJECTS})\b"
    index_concurrently = r"\bcreate(?:\s+unique)?\s+index\s+concurrently\b"
    return bool(re.search(create, uncommented, flags=re.IGNORECASE) or re.search(index_concurrently, uncommented, flags=re.IGNORECASE))


def validate_semantic_artifact(path: str, text: str, policy: dict) -> list[str]:
    errors = list(_ORIGINAL_VALIDATE_SEMANTIC_ARTIFACT(path, text, policy))
    if not any(path.startswith(prefix) for prefix in policy.get("semantic_scan_prefixes", [])):
        return errors
    decoded = _core._decode_identifier_escapes(text)
    errors.extend(_hardened_marker_errors(path, decoded, policy))
    if _has_hardened_persistence_write(decoded):
        errors.append(f"direct persistence write surface forbidden in G2 composition: {path}")
    if _has_hardened_secret_flow(decoded):
        errors.append(f"raw secret persistence/exposure data-flow forbidden in G2: {path}")
    if _has_hardened_ddl(decoded):
        errors.append(f"G2-owned DDL forbidden; accepted Monitoring persistence must be reused: {path}")
    return list(dict.fromkeys(errors))


_core.validate_semantic_artifact = validate_semantic_artifact


def parse_labels(value: str) -> set[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError("labels JSON must be an array of strings")
    return set(parsed)


def main() -> int:
    parser = argparse.ArgumentParser()
    for arg in ("base", "head", "head-ref", "labels-json", "head-repo", "base-repo"):
        parser.add_argument(f"--{arg}", required=True)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        labels = parse_labels(args.labels_json)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: invalid labels metadata: {exc}", file=sys.stderr)
        return 1
    _classified, errors = validate(args.base, args.head, args.head_ref, labels, args.head_repo, args.base_repo, root=args.repo_root)
    for error in errors:
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g2_implementation_scope=PASS classification=trusted_explicit_attestation path_scope=allowlisted semantic_scope=structural+bounded+taint-sequence readiness=live-source-authenticated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
