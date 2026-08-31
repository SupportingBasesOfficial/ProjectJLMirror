from __future__ import annotations

import cache_authority_conformance_integrity_runner as integrity

final = integrity.final
core = integrity.core


def fill_composed_positive(resources: dict[str, str], generations: dict[str, int]) -> None:
    core.cache_cmd(
        "HSET",
        final.composed_positive_key(resources["identity"]),
        "session_gen", str(generations["identity"]),
        "membership_gen", str(generations["membership"]),
        "authz_gen", str(generations["authz"]),
        "platform_gen", str(generations["platform"]),
    )


def main() -> int:
    # The final runner already uses this exact composed-positive representation
    # in its canonical scenario; expose the same operation to the integrity
    # scope-binding negative control without changing admission semantics.
    final.fill_composed_positive = fill_composed_positive
    return integrity.main()


if __name__ == "__main__":
    raise SystemExit(main())
