#!/usr/bin/env python3
from __future__ import annotations

import json
import validate_g4_metrics_authorization as auth


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    manifest = json.loads(auth.MANIFEST.read_text(encoding="utf-8"))
    require(auth.AUTH_ID == "g4.metrics@1", "authorization id drift")
    require("apps/g4-metrics/" in auth.EXPECTED_PREFIXES, "canonical G4 app prefix missing")
    require("sql/g4/" not in auth.EXPECTED_PREFIXES, "G4 must not gain parallel SQL authority")
    require("src/jlmirror_g4/" not in auth.EXPECTED_PREFIXES, "G4 must not gain parallel domain-source authority")
    require(".github/workflows/g4-metrics-runtime.yml" in auth.EXPECTED_EXACT, "bounded runtime workflow missing")
    forbidden = set(manifest["explicitly_not_authorized"])
    require("problem_product_surface" in forbidden, "G5 Problem exclusion missing")
    require("health_product_surface" in forbidden, "G5 Health exclusion missing")
    require("metric_derived_health_or_problem_authority" in forbidden, "metric-derived G5 authority exclusion missing")
    require("direct_provider_passthrough" in forbidden, "provider passthrough exclusion missing")
    print("g4_authorization_falsification=PASS sql_parallel=blocked domain_parallel=blocked g5=blocked provider_passthrough=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
