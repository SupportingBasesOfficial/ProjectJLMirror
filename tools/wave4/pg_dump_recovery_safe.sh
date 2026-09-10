#!/usr/bin/env bash
set -euo pipefail

# Canonical logical recovery/relocation dump entrypoint for Wave 4 Monitoring.
# Runtime admission is placement/recovery-local authority and MUST never be
# copied into a recovered database. UNLOGGED alone is insufficient because
# pg_dump includes unlogged-table data unless it is explicitly excluded.
exec pg_dump \
  --exclude-table-data=monitoring.monitoring_host_inventory_runtime_admission \
  --exclude-table-data=monitoring.monitoring_metric_definition_runtime_admission \
  "$@"
