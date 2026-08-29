#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: tenant_relocation.sh <tier1-postgres-container> <tier2-timescale-container>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Fail before any evidence state is mutated if one of the protocol modules is
# syntactically invalid. The modules are sourced in authority order so the
# target verifier exists before the Tier 1 receipt/activation tests execute.
for module in \
  tenant_relocation_tier1.sh \
  tenant_relocation_tier2.sh \
  tenant_relocation_tier1_atomic.sh \
  tenant_relocation_tests.sh
do
  bash -n "$ROOT/$module"
done

# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tier1.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tier2.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tier1_atomic.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tests.sh"
