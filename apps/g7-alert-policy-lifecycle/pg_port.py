from __future__ import annotations

import json
from typing import Any


def _decode(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


class PgAlertPolicyLifecycleGateway:
    """DB-API gateway restricted to G7 SECURITY DEFINER functions."""

    def __init__(self, connection: Any):
        self.connection = connection

    def _scalar(self, statement: str, params: tuple[Any, ...]) -> Any:
        with self.connection.cursor() as cursor:
            cursor.execute(statement, params)
            row = cursor.fetchone()
        if row is None:
            return None
        return _decode(row[0])

    def create_policy_version(
        self,
        tenant_id: str,
        policy_id: str,
        policy_version: int,
        source_kind: str,
        problem_min_severity: str | None,
        health_classes: tuple[str, ...],
        monitoring_source_id: str | None = None,
        monitoring_resource_id: str | None = None,
    ) -> dict:
        return self._scalar(
            "SELECT alerting.g7_create_policy_version(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                tenant_id,policy_id,policy_version,source_kind,problem_min_severity,
                list(health_classes),monitoring_source_id,monitoring_resource_id,
            ),
        )

    def set_effective_policy_version(
        self, tenant_id: str, policy_id: str, policy_version: int, enabled: bool
    ) -> dict:
        return self._scalar(
            "SELECT alerting.g7_set_effective_policy_version(%s,%s,%s,%s)",
            (tenant_id,policy_id,policy_version,enabled),
        )

    def evaluate_current(
        self, tenant_id: str, policy_id: str, policy_version: int, source_subject_id: str
    ) -> dict:
        return self._scalar(
            "SELECT alerting.g7_apply_current_evaluation(%s,%s,%s,%s)",
            (tenant_id,policy_id,policy_version,source_subject_id),
        )

    def list_alerts(self, tenant_id: str, limit: int) -> list[dict]:
        value=self._scalar(
            "SELECT alerting.g7_list_alerts(%s,%s)",
            (tenant_id,limit),
        )
        return list(value or [])

    def get_alert(self, tenant_id: str, alert_id: str) -> dict | None:
        return self._scalar(
            "SELECT alerting.g7_get_alert(%s,%s)",
            (tenant_id,alert_id),
        )
