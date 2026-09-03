from __future__ import annotations

import validate_controlflow_authority_and_bracket_calls_v4 as v4


def _resolve_alias_preserving_self_identity(name: str, state: v4.BaseState) -> str | None:
    """Resolve aliases while treating `X -> X` import bindings as stable identity.

    A direct imported name such as `from typing import Protocol` is represented by
    `Protocol -> Protocol`. That is not an alias cycle and must remain a valid
    ordinary lexical base. Multi-symbol cycles and explicitly unresolved aliases
    still fail closed.
    """
    seen: set[str] = set()
    current = name
    while True:
        if current not in state.aliases:
            return current
        next_name = state.aliases[current]
        if next_name is None:
            return None
        if next_name == current:
            return current
        if current in seen or next_name in seen:
            return None
        seen.add(current)
        current = next_name


v4._resolve_alias = _resolve_alias_preserving_self_identity


if __name__ == "__main__":
    raise SystemExit(v4.main())
