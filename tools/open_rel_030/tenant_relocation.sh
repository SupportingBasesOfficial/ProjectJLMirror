#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: tenant_relocation.sh <tier1-postgres-container> <tier2-timescale-container>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Fail before any evidence state is mutated if one of the protocol modules is
# syntactically invalid. Modules are sourced in authority order; isolated
# activation atomicity is falsified before the main relocation scenario.
for module in \
  tenant_relocation_tier1.sh \
  tenant_relocation_tier2.sh \
  tenant_relocation_verifier_hardening.sh \
  tenant_relocation_tier1_atomic.sh \
  tenant_relocation_atomicity_tests.sh \
  tenant_relocation_tests.sh
do
  bash -n "$ROOT/$module"
done

# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tier1.sh"

# The old controller-generated entropy is deliberately discarded before the
# target authority is initialized. The effective checkpoint signing key is
# generated only inside Tier 2 by gen_random_bytes and is never returned here.
unset attestation_key

# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tier2.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_verifier_hardening.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tier1_atomic.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_atomicity_tests.sh"
# shellcheck source=/dev/null
source "$ROOT/tenant_relocation_tests.sh"
