#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import validate_g3_resource_inventory_authorization as auth


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(auth.AUTH_ID == "g3.resource-inventory@1", "authorization id drift")
    require("apps/g3-resource-inventory/" in auth.EXPECTED_PREFIXES, "canonical G3 app prefix missing")
    require("sql/g3/" not in auth.EXPECTED_PREFIXES, "G3 must not gain parallel SQL authority")
    require("src/jlmirror_g3/" not in auth.EXPECTED_PREFIXES, "G3 must not gain parallel domain-source authority")
    require(".github/workflows/g3-resource-inventory-runtime.yml" in auth.EXPECTED_EXACT, "bounded runtime workflow missing")
    require("metric_definition_or_metric_value_product_surface" in json.loads(auth.MANIFEST.read_text())["explicitly_not_authorized"], "G4 exclusion missing")
    print("g3_authorization_falsification=PASS sql_parallel=blocked domain_parallel=blocked g4=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
