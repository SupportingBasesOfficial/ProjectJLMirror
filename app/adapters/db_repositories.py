"""DB-backed repository implementations for monitoring workers.

Uses the database_migration_url (superuser) connection so workers can query
pending operations across all tenants without RLS restrictions and call stored
procs that are restricted by role (host inventory functions).

TODO(prod): replace with a dedicated worker role that has precisely the grants
needed for each responsibility kind.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from jlmirror_monitoring import InitialValidationClaim, InitialValidationResult
from jlmirror_monitoring.host_inventory import HostInventoryClaim, HostInventoryResult
from jlmirror_monitoring.metric_current_state import (
    CurrentMetricTarget,
    MetricCurrentStateClaim,
    MetricCurrentStateResult,
    MetricValueKind,
)
from jlmirror_monitoring.metric_definitions import (
    MetricDefinitionClaim,
    MetricDefinitionResult,
    ZabbixItemEvidence,
    ZabbixNativeValueType,
    ZabbixItemOperationalState,
)
from jlmirror_monitoring.source import ConfiguredProviderScope, ZabbixProviderConfiguration

from app.config import settings

logger = logging.getLogger(__name__)

_MAX_PENDING_PER_CYCLE = 10


def _admin_conn(**kwargs: Any) -> psycopg.Connection:
    return psycopg.connect(settings.database_migration_url, row_factory=dict_row, **kwargs)


def _parse_scope(scope_raw: Any) -> ConfiguredProviderScope:
    if isinstance(scope_raw, str):
        scope_raw = json.loads(scope_raw)
    return ConfiguredProviderScope(host_group_refs=tuple(scope_raw.get("host_group_refs", [])))


def fetch_pending_ops(responsibility_kind: str, limit: int = _MAX_PENDING_PER_CYCLE) -> list[dict[str, str]]:
    """Return (tenant_id, monitoring_sync_operation_id) pairs pending a given responsibility."""
    with _admin_conn(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tenant_id, monitoring_sync_operation_id
                  FROM monitoring.monitoring_sync_operation
                 WHERE responsibility_kind = %s
                   AND state = 'pending'
                   AND claim_token IS NULL
                 LIMIT %s
                """,
                (responsibility_kind, limit),
            )
            return cur.fetchall()


class DbMonitoringValidationRepository:
    """Satisfies MonitoringValidationRepository Protocol via stored procs."""

    def __init__(self, conn: psycopg.Connection, tenant_id: str) -> None:
        self._conn = conn
        self._tenant_id = tenant_id

    def claim_initial_validation(
        self, monitoring_sync_operation_id: str, *, claim_token: str
    ) -> InitialValidationClaim:
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    "SELECT * FROM monitoring.claim_zabbix_initial_validation(%s, %s, %s)",
                    (self._tenant_id, monitoring_sync_operation_id, claim_token),
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError("claim_zabbix_initial_validation returned no rows")
        return InitialValidationClaim(
            claim_token=claim_token,
            tenant_id=self._tenant_id,
            monitoring_sync_operation_id=monitoring_sync_operation_id,
            monitoring_source_id=row["monitoring_source_id"],
            provider_scope_tenant_binding_id=row["provider_scope_tenant_binding_id"],
            source_instance_generation=row["source_instance_generation"],
            configuration_revision=row["configuration_revision"],
            scope_revision=row["scope_revision"],
            provider_instance_ref=row["provider_instance_ref"],
            provider_configuration=ZabbixProviderConfiguration(base_url=row["provider_base_url"]),
            credential_binding_ref=row["credential_binding_ref"],
            configured_provider_scope=_parse_scope(row["configured_provider_scope"]),
        )

    def complete_initial_validation(
        self,
        claim: InitialValidationClaim,
        result: InitialValidationResult,
        *,
        validation_evidence_id: str,
    ) -> None:
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    """
                    SELECT monitoring.complete_zabbix_initial_validation(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        self._tenant_id,
                        claim.monitoring_sync_operation_id,
                        claim.claim_token,
                        validation_evidence_id,
                        claim.provider_scope_tenant_binding_id,
                        claim.provider_instance_ref,
                        result.operational_evidence_state.value,
                        result.operation_state.value,
                        result.failure_class.value if result.failure_class else None,
                        Jsonb(list(result.visible_host_group_refs)),
                        Jsonb(list(result.missing_host_group_refs)),
                        result.egress_decision_ref,
                        result.credential_generation_ref,
                    ),
                )


class DbMonitoringHostInventoryRepository:
    """Satisfies MonitoringHostInventoryRepository Protocol via stored procs."""

    def __init__(self, conn: psycopg.Connection, tenant_id: str) -> None:
        self._conn = conn
        self._tenant_id = tenant_id

    def claim_host_inventory(
        self, monitoring_sync_operation_id: str, *, claim_token: str
    ) -> HostInventoryClaim:
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    "SELECT * FROM monitoring.claim_zabbix_host_inventory(%s, %s, %s)",
                    (self._tenant_id, monitoring_sync_operation_id, claim_token),
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError("claim_zabbix_host_inventory returned no rows")
        return HostInventoryClaim(
            claim_token=claim_token,
            tenant_id=self._tenant_id,
            monitoring_sync_operation_id=monitoring_sync_operation_id,
            monitoring_source_id=row["monitoring_source_id"],
            provider_scope_tenant_binding_id=row["provider_scope_tenant_binding_id"],
            source_instance_generation=row["source_instance_generation"],
            configuration_revision=row["configuration_revision"],
            scope_revision=row["scope_revision"],
            provider_instance_ref=row["provider_instance_ref"],
            provider_configuration=ZabbixProviderConfiguration(base_url=row["provider_base_url"]),
            credential_binding_ref=row["credential_binding_ref"],
            configured_provider_scope=_parse_scope(row["configured_provider_scope"]),
        )

    def complete_host_inventory(
        self,
        claim: HostInventoryClaim,
        result: HostInventoryResult,
        *,
        snapshot_evidence_id: str,
    ) -> HostInventoryResult:
        hosts_payload = [host.canonical_evidence() for host in result.hosts]
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    """
                    SELECT monitoring.complete_zabbix_host_inventory(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        self._tenant_id,
                        claim.monitoring_sync_operation_id,
                        claim.claim_token,
                        snapshot_evidence_id,
                        claim.provider_scope_tenant_binding_id,
                        claim.provider_instance_ref,
                        result.operational_evidence_state.value,
                        result.operation_state.value,
                        result.failure_class.value if result.failure_class else None,
                        result.snapshot_complete,
                        Jsonb(hosts_payload),
                        result.egress_decision_ref,
                        result.credential_generation_ref,
                    ),
                )
        return result


def _canonical_value_json(v: Any) -> Any:
    """Convert a CanonicalMetricValue to a JSON-serializable form for JSONB storage."""
    if isinstance(v, Decimal):
        return float(v)
    return v


_LIST_TARGETS_LIMIT = 1000


class DbMonitoringMetricDefinitionRepository:
    """Satisfies MonitoringMetricDefinitionRepository Protocol via stored procs."""

    def __init__(self, conn: psycopg.Connection, tenant_id: str) -> None:
        self._conn = conn
        self._tenant_id = tenant_id

    def claim_metric_definitions(
        self, monitoring_sync_operation_id: str, *, claim_token: str
    ) -> MetricDefinitionClaim:
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    "SELECT * FROM monitoring.claim_zabbix_metric_definitions(%s, %s, %s)",
                    (self._tenant_id, monitoring_sync_operation_id, claim_token),
                )
                row = cur.fetchone()
        if row is None:
            raise RuntimeError("claim_zabbix_metric_definitions returned no rows")
        return MetricDefinitionClaim(
            claim_token=claim_token,
            tenant_id=self._tenant_id,
            monitoring_sync_operation_id=monitoring_sync_operation_id,
            monitoring_source_id=row["monitoring_source_id"],
            provider_scope_tenant_binding_id=row["provider_scope_tenant_binding_id"],
            source_instance_generation=row["source_instance_generation"],
            configuration_revision=row["configuration_revision"],
            scope_revision=row["scope_revision"],
            item_definition_poll_epoch=row["item_definition_poll_epoch"],
            item_definition_poll_generation=row["item_definition_poll_generation"],
            provider_instance_ref=row["provider_instance_ref"],
            provider_configuration=ZabbixProviderConfiguration(base_url=row["provider_base_url"]),
            credential_binding_ref=row["credential_binding_ref"],
            configured_provider_scope=_parse_scope(row["configured_provider_scope"]),
        )

    def complete_metric_definitions(
        self,
        claim: MetricDefinitionClaim,
        result: MetricDefinitionResult,
        *,
        snapshot_evidence_id: str,
    ) -> MetricDefinitionResult:
        items_payload = [
            {
                "itemid": item.itemid,
                "hostid": item.hostid,
                "name": item.name,
                "key": item.key,
                "unit": item.unit,
                "native_value_type": item.native_value_type.value,
                "operational_state": item.operational_state.value,
            }
            for item in result.items
        ]
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    """
                    SELECT monitoring.complete_zabbix_metric_definitions(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        self._tenant_id,
                        claim.monitoring_sync_operation_id,
                        claim.claim_token,
                        snapshot_evidence_id,
                        result.operational_evidence_state.value,
                        result.operation_state.value,
                        result.failure_class.value if result.failure_class else None,
                        result.egress_decision_ref,
                        result.credential_generation_ref,
                        result.snapshot_complete,
                        Jsonb(items_payload),
                    ),
                )
        return result


class DbMonitoringMetricCurrentStateRepository:
    """Satisfies MonitoringMetricCurrentStateRepository Protocol via stored procs."""

    def __init__(self, conn: psycopg.Connection, tenant_id: str) -> None:
        self._conn = conn
        self._tenant_id = tenant_id

    def claim_metric_current_state(
        self, monitoring_sync_operation_id: str, *, claim_token: str
    ) -> MetricCurrentStateClaim:
        targets: list[CurrentMetricTarget] = []
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    "SELECT * FROM monitoring.claim_zabbix_metric_current_state(%s, %s, %s)",
                    (self._tenant_id, monitoring_sync_operation_id, claim_token),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("claim_zabbix_metric_current_state returned no rows")

                cursor: str | None = None
                while True:
                    cur.execute(
                        """
                        SELECT * FROM monitoring.list_zabbix_metric_current_targets(
                            %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            self._tenant_id,
                            monitoring_sync_operation_id,
                            claim_token,
                            cursor,
                            _LIST_TARGETS_LIMIT,
                        ),
                    )
                    page = cur.fetchall()
                    for r in page:
                        targets.append(
                            CurrentMetricTarget(
                                metric_definition_id=r["metric_definition_id"],
                                monitoring_resource_id=r["monitoring_resource_id"],
                                provider_external_ref=r["provider_external_ref"],
                                value_kind=MetricValueKind(r["value_kind"]),
                            )
                        )
                    if len(page) < _LIST_TARGETS_LIMIT:
                        break
                    cursor = page[-1]["metric_definition_id"]

        return MetricCurrentStateClaim(
            claim_token=claim_token,
            tenant_id=self._tenant_id,
            monitoring_sync_operation_id=monitoring_sync_operation_id,
            monitoring_source_id=row["monitoring_source_id"],
            source_instance_generation=row["source_instance_generation"],
            configuration_revision=row["configuration_revision"],
            scope_revision=row["scope_revision"],
            current_state_poll_epoch=row["current_state_poll_epoch"],
            current_state_poll_generation=row["current_state_poll_generation"],
            provider_instance_ref=row["provider_instance_ref"],
            provider_configuration=ZabbixProviderConfiguration(base_url=row["provider_base_url"]),
            credential_binding_ref=row["credential_binding_ref"],
            targets=tuple(targets),
        )

    def complete_metric_current_state(
        self,
        claim: MetricCurrentStateClaim,
        result: MetricCurrentStateResult,
    ) -> MetricCurrentStateResult:
        observations_payload = [
            {
                "metric_definition_id": obs.metric_definition_id,
                "provider_external_ref": obs.provider_external_ref,
                "observation_id": obs.observation_id,
                "provider_clock": obs.observed_at_epoch_seconds,
                "provider_ns": obs.observed_at_nanoseconds,
                "value_kind": obs.value_kind.value,
                "canonical_value": _canonical_value_json(obs.canonical_value),
            }
            for obs in result.accepted_observations
        ]
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (self._tenant_id,))
                cur.execute(
                    "SELECT monitoring.complete_zabbix_metric_current_state(%s, %s, %s, %s)",
                    (
                        self._tenant_id,
                        claim.monitoring_sync_operation_id,
                        claim.claim_token,
                        Jsonb(observations_payload),
                    ),
                )
        return result
