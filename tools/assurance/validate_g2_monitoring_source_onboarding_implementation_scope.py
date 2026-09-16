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
_DDL_MODIFIERS = "temp|temporary|unlogged|unique|concurrently|global|local|recursive"
_DDL_OBJECTS = rf"(?:{_core.DDL_OBJECTS}|database|foreign\s+table|tablespace|server|system|foreign\s+data\s+wrapper|user\s+mapping|publication|subscription|role|user|group|domain|aggregate|collation|(?:default\s+)?conversion|(?:trusted\s+)?(?:procedural\s+)?language|operator(?:\s+(?:class|family))?|statistics|rule|access\s+method|(?:constraint\s+)?trigger|event\s+trigger|routine|cast|transform|default\s+privileges|large\s+object|owned|text\s+search\s+(?:configuration|dictionary|parser|template))"


def _reflect_apply_prefix() -> str:
    member = r"\bReflect\s*(?:\.\s*apply|\[\s*['\"`]apply['\"`]\s*\])"
    return rf"(?:\(\s*)*{member}(?:\s*\))*\s*\("


def _decode_executable_escapes(text: str) -> str:
    # JavaScript removes escaped physical line terminators before evaluating string contents.
    continued = re.sub(r"\\(?:\r\n|[\n\r\u2028\u2029])", "", text)
    decoded = _core._decode_identifier_escapes(continued)

    def replace_hex(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    return re.sub(r"\\x([0-9A-Fa-f]{2})", replace_hex, decoded)


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


def _separator_sequence_hit(text: str, marker: str) -> bool:
    parts = _core._split_components(marker)
    if len(parts) < 2:
        return False
    atoms: list[str] = []
    for part in parts:
        variants = sorted(_core._identifier_variants(part), key=len, reverse=True)
        atoms.append("(?:" + "|".join(re.escape(value) for value in variants) + ")")
    pattern = r"(?<![A-Za-z0-9_$])" + r"[^A-Za-z0-9_$]+".join(atoms) + r"(?![A-Za-z0-9_$])"
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _hardened_marker_errors(path: str, decoded: str, policy: dict) -> list[str]:
    errors: list[str] = []
    scan_text = re.sub(r"\bbrowser[\s_-]+automation\b", "browser_e2e", decoded, flags=re.IGNORECASE)
    identifiers = _core._raw_identifiers(scan_text)
    for marker in policy.get("forbidden_code_markers", []):
        if marker in _core.STRUCTURAL_MARKERS:
            continue
        if any(_component_sequence_hit(identifier, marker) for identifier in identifiers) or _separator_sequence_hit(scan_text, marker):
            errors.append(f"forbidden G2 semantic code marker '{marker}' in {path}")
    return errors


def _persistence_aliases(decoded: str) -> set[str]:
    aliases = set(_core.PERSISTENCE_RECEIVERS)
    changed = True
    while changed:
        changed = False
        receiver = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
        grouped_receiver = rf"(?:\(\s*)*(?:{receiver})(?:\s*\))*"
        patterns = (
            rf"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*{grouped_receiver}\s*(?:[;\n]|$)",
            rf"(?<![A-Za-z0-9_$])([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*{grouped_receiver}\s*(?:[;\n]|$)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
                alias = match.group(1)
                if alias not in aliases:
                    aliases.add(alias)
                    changed = True
    return aliases


def _strip_balanced_parentheses(value: str) -> str:
    value = value.strip()
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        quote: str | None = None
        escaped = False
        encloses_all = True
        for index, char in enumerate(value):
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in "'\"`":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    encloses_all = False
                    break
        if not encloses_all or depth != 0:
            break
        value = value[1:-1].strip()
    return value


def _split_static_concat(expr: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(expr):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "+" and depth == 0:
            pieces.append(expr[start:index])
            start = index + 1
    pieces.append(expr[start:])
    return pieces


def _split_top_level_commas(expr: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    quote: str | None = None
    escaped = False
    for index, char in enumerate(expr):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] = max(0, depths[closing[char]] - 1)
        elif char == "," and not any(depths.values()):
            pieces.append(expr[start:index])
            start = index + 1
    pieces.append(expr[start:])
    return pieces


def _variable_declarators(text: str) -> list[tuple[str, str]]:
    declarators: list[tuple[str, str]] = []
    for start_match in re.finditer(r"\b(?:const|let|var)\s+", text):
        start = start_match.end()
        depths = {"(": 0, "[": 0, "{": 0}
        closing = {")": "(", "]": "[", "}": "{"}
        quote: str | None = None
        escaped = False
        end = len(text)
        for index in range(start, len(text)):
            char = text[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in "'\"`":
                quote = char
            elif char in depths:
                depths[char] += 1
            elif char in closing:
                depths[closing[char]] = max(0, depths[closing[char]] - 1)
            elif not any(depths.values()) and char == ";":
                end = index
                break
            elif not any(depths.values()) and char == "\n":
                end = index
                break
        for item in _split_top_level_commas(text[start:end]):
            match = re.fullmatch(r"\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(.+?)\s*", item)
            if match:
                declarators.append((match.group(1), match.group(2)))
    return declarators


def _static_computed_member(expr: str) -> str | None:
    expr = _strip_balanced_parentheses(expr)
    pieces = _split_static_concat(expr)
    values: list[str] = []
    for piece in pieces:
        piece = _strip_balanced_parentheses(piece)
        match = re.fullmatch(r"([\'\"`])([^\'\"`]*)\1", piece)
        if not match or (match.group(1) == "`" and "${" in match.group(2)):
            return None
        values.append(match.group(2))
    return "".join(values).casefold()


def _fold_static_string_concatenations(text: str) -> str:
    literal = r"(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|\`(?:\\.|[^\`\\])*\`)"
    grouped_literal = rf"(?:\(\s*)*{literal}(?:\s*\))*"
    pattern = re.compile(rf"{grouped_literal}(?:\s*\+\s*{grouped_literal})+")
    previous = None
    while previous != text:
        previous = text

        def replace(match: re.Match[str]) -> str:
            value = _static_computed_member(match.group(0))
            return json.dumps(value) if value is not None else match.group(0)

        text = pattern.sub(replace, text)
    return text


def _resolve_static_computed_aliases(text: str) -> str:
    aliases: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for name, expression in _variable_declarators(text):
            value = _static_computed_member(expression)
            if value is None and re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", expression):
                value = aliases.get(expression)
            if value is not None and aliases.get(name) != value:
                aliases[name] = value
                changed = True
    if not aliases:
        return text
    names = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))

    def replace(match: re.Match[str]) -> str:
        return f"[{json.dumps(aliases[match.group(1)])}]"

    return re.sub(
        rf"\[\s*({names})\s*\]",
        replace,
        text,
    )


def _destructured_member_binding(item: str) -> tuple[str, str] | None:
    item = item.strip()
    if not item or item.startswith("..."):
        return None
    if item.startswith("["):
        close = item.find("]")
        if close < 0:
            return None
        source_name = _static_computed_member(item[1:close])
        remainder = item[close + 1:].strip()
        if source_name is None or not remainder.startswith(":"):
            return None
        target = remainder[1:].split("=", 1)[0].strip()
    else:
        pair = [part.strip() for part in item.split(":", 1)]
        source_name = pair[0].split("=", 1)[0].strip().casefold()
        target = pair[-1].split("=", 1)[0].strip()
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", target):
        return None
    return source_name, target


def _invocation_suffix() -> str:
    return r"(?:\(|\?\.\s*\(|\.\s*(?:call|apply)\s*\(|\.\s*bind\s*\([^)]*\)\s*\()"


def _has_hardened_persistence_write(decoded: str) -> bool:
    aliases = _persistence_aliases(decoded)
    receiver = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    write = "|".join(re.escape(name) for name in sorted(_core.PERSISTENCE_WRITES, key=len, reverse=True))
    receiver_expr = rf"(?:\(\s*)*(?:{receiver})(?:\s*\))*"
    member_expr = rf"{receiver_expr}\s*(?:\?\.|\.)\s*(?:{write})"
    grouped_member_expr = rf"(?:\(\s*)*{member_expr}(?:\s*\))*"
    invoke = _invocation_suffix()
    direct_patterns = (
        rf"(?<![A-Za-z0-9_$]){grouped_member_expr}\s*{invoke}",
        rf"\b(?:const|let|var)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*{member_expr}\b",
        rf"\b(?:const|let|var)\s*\{{[^}}]*\b(?:{write})\b[^}}]*\}}\s*=\s*{receiver_expr}\b",
    )
    if any(re.search(pattern, decoded, flags=re.IGNORECASE) for pattern in direct_patterns):
        return True
    if re.search(
        rf"{_reflect_apply_prefix()}\s*{grouped_member_expr}\s*,",
        decoded,
        flags=re.IGNORECASE,
    ):
        return True

    computed_expr = rf"{receiver_expr}\s*(?:\?\.)?\s*\[([^\]]+)\]"
    grouped_computed_expr = rf"(?:\(\s*)*{computed_expr}(?:\s*\))*"
    for match in re.finditer(
        rf"(?<![A-Za-z0-9_$]){grouped_computed_expr}\s*{invoke}",
        decoded,
        flags=re.IGNORECASE,
    ):
        if _static_computed_member(match.group(1)) in _core.PERSISTENCE_WRITES:
            return True
    for match in re.finditer(
        rf"{_reflect_apply_prefix()}\s*{grouped_computed_expr}\s*,",
        decoded,
        flags=re.IGNORECASE,
    ):
        if _static_computed_member(match.group(1)) in _core.PERSISTENCE_WRITES:
            return True

    method_aliases: set[str] = set()
    alias_prefix = r"(?:(?:const|let|var)\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
    for match in re.finditer(rf"{alias_prefix}{member_expr}\b", decoded, flags=re.IGNORECASE):
        method_aliases.add(match.group(1))
    for match in re.finditer(rf"{alias_prefix}{computed_expr}", decoded, flags=re.IGNORECASE):
        if _static_computed_member(match.group(2)) in _core.PERSISTENCE_WRITES:
            method_aliases.add(match.group(1))
    destructuring_patterns = (
        rf"\b(?:const|let|var)\s*\{{([^}}]*)\}}\s*=\s*{receiver_expr}\b",
        rf"(?<![A-Za-z0-9_$])\(\s*\{{([^}}]*)\}}\s*=\s*{receiver_expr}\s*\)",
    )
    for pattern in destructuring_patterns:
        for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
            for item in match.group(1).split(","):
                binding = _destructured_member_binding(item)
                if binding is not None and binding[0] in _core.PERSISTENCE_WRITES:
                    method_aliases.add(binding[1])
    return any(
        re.search(rf"\b{re.escape(alias)}\s*{invoke}", decoded)
        or re.search(
            rf"{_reflect_apply_prefix()}\s*{re.escape(alias)}\s*,",
            decoded,
            flags=re.IGNORECASE,
        )
        for alias in method_aliases
    )


def _raw_secret_identifier(identifier: str) -> bool:
    parts = set(_core._split_components(identifier))
    if "credential" in parts and "binding" in parts and ("ref" in parts or "reference" in parts):
        return False
    return bool(parts & _core.SECRET_TERMS)


def _strip_plain_string_literals(text: str) -> str:
    chars = list(text)
    template_expressions: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if quote is None:
            if char == "`":
                start = index
                index += 1
                escaped_template = False
                while index < len(text):
                    current = text[index]
                    if escaped_template:
                        escaped_template = False
                    elif current == "\\":
                        escaped_template = True
                    elif current == "`":
                        break
                    index += 1
                end = min(index, len(text) - 1)
                segment = text[start + 1:end]
                template_expressions.extend(
                    match.group(1)
                    for match in re.finditer(r"\$\{(.*?)\}", segment, flags=re.DOTALL)
                )
                for position in range(start, end + 1):
                    chars[position] = " "
            elif char in "'\"":
                quote = char
                chars[index] = " "
        else:
            chars[index] = " "
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        index += 1
    return "".join(chars) + "\n" + "\n".join(template_expressions)


def _contains_secret_reference(text: str, tainted: set[str]) -> bool:
    for match in re.finditer(r"\[([^\]]+)\]", text):
        member = _static_computed_member(match.group(1))
        if member is not None and (member in tainted or _raw_secret_identifier(member)):
            return True
    code = _strip_plain_string_literals(text)
    for identifier in _core._raw_identifiers(code):
        if identifier in tainted:
            return True
    return False


def _secret_taint(decoded: str) -> set[str]:
    code = _strip_plain_string_literals(decoded)
    literal_backed = {
        name
        for name, expression in _variable_declarators(decoded)
        if _static_computed_member(expression) is not None
    }
    property_secret_names = {
        match.group(1)
        for match in re.finditer(r"\.\s*([A-Za-z_$][A-Za-z0-9_$]*)", code)
        if _raw_secret_identifier(match.group(1))
    }
    tainted = {
        identifier
        for identifier in _core._raw_identifiers(code)
        if _raw_secret_identifier(identifier)
        and (identifier not in literal_backed or identifier in property_secret_names)
    }
    changed = True
    while changed:
        changed = False
        for target, expression in _variable_declarators(decoded):
            if target not in tainted and _contains_secret_reference(expression, tainted):
                tainted.add(target)
                changed = True
        for match in re.finditer(r"(?<![=!<>A-Za-z0-9_$])([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:\?\?=|\|\|=|&&=|=(?!=|>))\s*([^;\n]+)", decoded):
            target, expression = match.group(1), match.group(2)
            if target not in tainted and _contains_secret_reference(expression, tainted):
                tainted.add(target)
                changed = True
        for match in re.finditer(r"\b(?:const|let|var)\s*\{([^}]*)\}\s*=\s*([^;\n]+)", decoded):
            bindings, source = match.group(1), match.group(2)
            source_tainted = _contains_secret_reference(source, tainted)
            for item in bindings.split(","):
                item = item.strip()
                if not item:
                    continue
                pair = [part.strip() for part in item.split(":", 1)]
                source_name = pair[0]
                target = pair[-1].split("=", 1)[0].strip()
                if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", target):
                    continue
                if _raw_secret_identifier(source_name) or (source_tainted and _raw_secret_identifier(target)):
                    if target not in tainted:
                        tainted.add(target)
                        changed = True
        for match in re.finditer(r"(?<![A-Za-z0-9_$])\(\s*\{([^}]*)\}\s*=\s*([^;\n)]+)\s*\)", decoded):
            bindings, source = match.group(1), match.group(2)
            source_tainted = _contains_secret_reference(source, tainted)
            for item in bindings.split(","):
                item = item.strip()
                if not item:
                    continue
                pair = [part.strip() for part in item.split(":", 1)]
                source_name = pair[0]
                target = pair[-1].split("=", 1)[0].strip()
                if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", target):
                    continue
                if _raw_secret_identifier(source_name) or (source_tainted and _raw_secret_identifier(target)):
                    if target not in tainted:
                        tainted.add(target)
                        changed = True
    return tainted


def _sink_call_contains(text: str, names: set[str]) -> bool:
    sink = "|".join(sorted(_core.SECRET_SINK_TERMS, key=len, reverse=True))
    invoke = r"(?:(?:\.\s*(?:call|apply)\s*)?\(|\.\s*bind\s*\([^)]*\)\s*\()"
    for match in re.finditer(
        rf"(?:\(\s*)*(?:\b[A-Za-z_$][A-Za-z0-9_$]*\s*\.)?\b(?:{sink})(?:\s*\))*\s*{invoke}(.*?)\)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if _contains_secret_reference(match.group(1), names):
            return True
    for match in re.finditer(
        rf"(?:\(\s*)*\b[A-Za-z_$][A-Za-z0-9_$]*\s*\[(?P<member>[^\]]+)\](?:\s*\))*\s*{invoke}(?P<args>.*?)\)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        member = _static_computed_member(match.group("member"))
        if member in _core.SECRET_SINK_TERMS and _contains_secret_reference(match.group("args"), names):
            return True
    if re.search(r"\breturn\s+\{", text) and _contains_secret_reference(text, names):
        return True
    return False


def _balanced_block(text: str, open_index: int) -> tuple[str, int] | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:index], index + 1
    return None


def _function_definitions(decoded: str) -> list[tuple[str, str, str]]:
    definitions: list[tuple[str, str, str]] = []
    for match in re.finditer(r"\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{", decoded):
        block = _balanced_block(decoded, match.end() - 1)
        if block is not None:
            body, _end = block
            definitions.append((match.group(1), match.group(2), body))
    arrow_patterns = (
        r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(([^)]*)\)\s*=>\s*",
        r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*",
    )
    for pattern in arrow_patterns:
        for match in re.finditer(pattern, decoded):
            start = match.end()
            if start < len(decoded) and decoded[start:start + 1] == "{":
                block = _balanced_block(decoded, start)
                if block is not None:
                    body, _end = block
                    definitions.append((match.group(1), match.group(2), body))
            else:
                end = decoded.find(";", start)
                body = decoded[start:] if end < 0 else decoded[start:end]
                definitions.append((match.group(1), match.group(2), body))
    return definitions


def _sink_wrappers(decoded: str) -> set[str]:
    wrappers: set[str] = set()
    definitions = _function_definitions(decoded)
    changed = True
    while changed:
        changed = False
        for name, params_text, body in definitions:
            params = {p.strip() for p in params_text.split(",") if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", p.strip())}
            if not params or name in wrappers:
                continue
            direct = _sink_call_contains(body, params)
            indirect = any(
                re.search(rf"\b{re.escape(wrapper)}\s*\((.*?)\)", body, flags=re.DOTALL)
                and _contains_secret_reference(body, params)
                for wrapper in wrappers
            )
            if direct or indirect:
                wrappers.add(name)
                changed = True
    return wrappers


def _has_hardened_secret_flow(decoded: str) -> bool:
    tainted = _secret_taint(decoded)
    if _sink_call_contains(decoded, tainted):
        return True
    if not tainted:
        return False
    for wrapper in _sink_wrappers(decoded):
        for match in re.finditer(rf"\b{re.escape(wrapper)}\s*\((.*?)\)", decoded, flags=re.DOTALL):
            if _contains_secret_reference(match.group(1), tainted):
                return True
    return False


def _has_hardened_ddl(decoded: str) -> bool:
    uncommented = _core._strip_comments(decoded.casefold())
    modifiers = rf"(?:\s+(?:{_DDL_MODIFIERS}))*"
    create = rf"\bcreate(?:\s+or\s+replace)?{modifiers}\s+{_DDL_OBJECTS}\b"
    index_concurrently = r"\bcreate(?:\s+unique)?\s+index\s+concurrently\b"
    index_nulls_distinct = r"\bcreate\s+unique\s+nulls\s+(?:not\s+)?distinct\s+index\b"
    foreign_table = r"\bcreate(?:\s+(?:global|local|temp|temporary|unlogged))*\s+foreign\s+table\b"
    alter_or_drop = rf"\b(?:alter|drop)\s+{_DDL_OBJECTS}\b"
    return bool(
        re.search(create, uncommented, flags=re.IGNORECASE)
        or re.search(index_concurrently, uncommented, flags=re.IGNORECASE)
        or re.search(index_nulls_distinct, uncommented, flags=re.IGNORECASE)
        or re.search(foreign_table, uncommented, flags=re.IGNORECASE)
        or re.search(alter_or_drop, uncommented, flags=re.IGNORECASE)
    )


def _provider_aliases(decoded: str) -> set[str]:
    aliases = {"provider"}
    changed = True
    while changed:
        changed = False
        source = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
        grouped_source = rf"(?:\(\s*)*(?:{source})(?:\s*\))*"
        patterns = (
            rf"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*{grouped_source}\s*(?:[;\n]|$)",
            rf"(?<![A-Za-z0-9_$])([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*{grouped_source}\s*(?:[;\n]|$)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
                alias = match.group(1)
                if alias not in aliases:
                    aliases.add(alias)
                    changed = True
    return aliases


def _provider_authority_related(decoded: str) -> bool:
    authority = "|".join(sorted(_core.PROVIDER_AUTHORITY_TERMS, key=len, reverse=True))
    aliases = _provider_aliases(decoded)
    provider = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    grouped_provider = rf"(?:\(\s*)*(?:{provider})(?:\s*\))*"
    destructuring_patterns = (
        rf"\b(?:const|let|var)\s*\{{([^}}]*)\}}\s*=\s*{grouped_provider}(?=\s*(?:[;\n]|$))",
        rf"(?<![A-Za-z0-9_$])\(\s*\{{([^}}]*)\}}\s*=\s*{grouped_provider}\s*\)",
    )
    for pattern in destructuring_patterns:
        for match in re.finditer(pattern, decoded, flags=re.IGNORECASE):
            for item in match.group(1).split(","):
                binding = _destructured_member_binding(item)
                if binding is not None and binding[0] in _core.PROVIDER_AUTHORITY_TERMS:
                    return True
    direct_patterns = (
        rf"\b(?:{provider})\s*(?:\?\.|\.)\s*(?:{authority})\b",
        rf"\b(?:{provider})\s*\[\s*['\"](?:{authority})['\"]\s*\]",
        rf"\b(?:{authority})\s*(?:\?\.|\.)\s*(?:{provider})\b",
    )
    if any(re.search(pattern, decoded, flags=re.IGNORECASE) for pattern in direct_patterns):
        return True
    for alias in aliases:
        for match in re.finditer(rf"\b{re.escape(alias)}\s*\[([^\]]+)\]", decoded, flags=re.IGNORECASE):
            member = _static_computed_member(match.group(1))
            if member in _core.PROVIDER_AUTHORITY_TERMS:
                return True
    for identifier in _core._raw_identifiers(decoded):
        parts = _core._split_components(identifier)
        if len(parts) != 2:
            continue
        for index in range(len(parts) - 1):
            pair = {parts[index], parts[index + 1]}
            if pair & {alias.casefold() for alias in aliases} and pair & _core.PROVIDER_AUTHORITY_TERMS:
                return True
    return False


def validate_semantic_artifact(path: str, text: str, policy: dict) -> list[str]:
    errors = list(_ORIGINAL_VALIDATE_SEMANTIC_ARTIFACT(path, text, policy))
    if not any(path.startswith(prefix) for prefix in policy.get("semantic_scan_prefixes", [])):
        return errors
    decoded = _decode_executable_escapes(text)
    decoded = _fold_static_string_concatenations(decoded)
    decoded = _resolve_static_computed_aliases(decoded)

    if any(ord(char) > 127 for char in path):
        errors.append(f"non-ASCII/confusable path forbidden in governed G2 artifact: {path}")

    provider_error = f"provider-native authorization/authority semantics forbidden in G2: {path}"
    if provider_error in errors and not _provider_authority_related(decoded):
        errors = [error for error in errors if error != provider_error]

    secret_error = f"raw secret persistence/exposure data-flow forbidden in G2: {path}"
    hardened_secret_flow = _has_hardened_secret_flow(decoded)
    if secret_error in errors and not hardened_secret_flow:
        errors = [error for error in errors if error != secret_error]

    errors.extend(_hardened_marker_errors(path, decoded, policy))
    if _has_hardened_persistence_write(decoded):
        errors.append(f"direct persistence write surface forbidden in G2 composition: {path}")
    if hardened_secret_flow:
        errors.append(secret_error)
    if _has_hardened_ddl(decoded):
        errors.append(f"G2-owned DDL forbidden; accepted Monitoring persistence must be reused: {path}")
    if _provider_authority_related(decoded):
        errors.append(provider_error)
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
    _classified, errors = validate(
        args.base,
        args.head,
        args.head_ref,
        labels,
        args.head_repo,
        args.base_repo,
        root=args.repo_root,
    )
    for error in errors:
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(
        "g2_implementation_scope=PASS classification=trusted_explicit_attestation "
        "path_scope=allowlisted semantic_scope=structural+bounded+taint-sequence readiness=live-source-authenticated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
