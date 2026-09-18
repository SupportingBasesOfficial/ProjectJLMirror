from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

READ_ACTION = "monitoring.resource.read"


@dataclass(frozen=True)
class CurrentAuthorizationEvidence:
    actor_principal_id: str
    actor_principal_kind: str
    actor_generation_ref: str
    authorization_decision_ref: str


@dataclass(frozen=True)
class ResourceRecord:
    monitoring_resource_id: str
    monitoring_source_id: str
    source_instance_generation: str
    generation_state: str
    display_name: str
    resource_kind: str
    scope_state: str
    scope_projection_revision: int
    scope_evidence_state: str
    presence_state: str
    presence_evidence_state: str
    provider_object_kind: str
    provider_external_ref: str | None
    last_observed_at: str | None
    last_confirmed_present_at: str | None
    created_at: str
    updated_at: str


class CurrentAuthorizationPort(Protocol):
    @property
    def actor_ref(self) -> str: ...

    def require(
        self,
        *,
        actor_ref: str,
        tenant_id: str,
        action: str,
    ) -> CurrentAuthorizationEvidence: ...


class ResourceReadPort(Protocol):
    def list_active(self, *, tenant_id: str) -> Sequence[ResourceRecord]: ...

    def get(self, *, tenant_id: str, monitoring_resource_id: str) -> ResourceRecord | None: ...


class ResourceInventory:
    def __init__(self, *, repository: ResourceReadPort, authorization: CurrentAuthorizationPort) -> None:
        self._repository = repository
        self._authorization = authorization

    def _admit(self, tenant_id: str) -> CurrentAuthorizationEvidence:
        return self._authorization.require(
            actor_ref=self._authorization.actor_ref,
            tenant_id=tenant_id,
            action=READ_ACTION,
        )

    def list_current(self, *, tenant_id: str) -> dict:
        self._admit(tenant_id)
        rows = tuple(self._repository.list_active(tenant_id=tenant_id))
        self._admit(tenant_id)

        items = [self._list_item(row) for row in rows]
        return {
            "generation_state": "active_generation",
            "items": items,
            "next_cursor": None,
        }

    def get_detail(self, *, tenant_id: str, monitoring_resource_id: str) -> dict | None:
        if not monitoring_resource_id or len(monitoring_resource_id) > 512:
            raise ValueError("monitoring_resource_id must be bounded non-empty text")

        self._admit(tenant_id)
        row = self._repository.get(
            tenant_id=tenant_id,
            monitoring_resource_id=monitoring_resource_id,
        )
        self._admit(tenant_id)
        if row is None:
            return None
        return self._detail_item(row)

    @staticmethod
    def _base(row: ResourceRecord) -> dict:
        if row.resource_kind != "host":
            raise RuntimeError("G3 may expose only accepted host resources")
        if row.provider_object_kind != "zabbix_host":
            raise RuntimeError("G3 provider evidence kind is outside accepted scope")
        if row.generation_state not in {"active_generation", "historical_generation"}:
            raise RuntimeError("resource generation state is invalid")
        if row.scope_state not in {"in_scope", "out_of_scope"}:
            raise RuntimeError("resource scope state is invalid")
        if row.presence_state not in {"present", "removed"}:
            raise RuntimeError("resource presence state is invalid")

        return {
            "monitoring_resource_id": row.monitoring_resource_id,
            "monitoring_source_id": row.monitoring_source_id,
            "source_instance_generation": row.source_instance_generation,
            "generation_state": row.generation_state,
            "display_name": row.display_name,
            "resource_kind": row.resource_kind,
            "scope_state": row.scope_state,
            "scope_projection_revision": row.scope_projection_revision,
            "scope_evidence_state": row.scope_evidence_state,
            "presence_state": row.presence_state,
            "presence_evidence_state": row.presence_evidence_state,
            "last_observed_at": row.last_observed_at,
            "last_confirmed_present_at": row.last_confirmed_present_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @classmethod
    def _list_item(cls, row: ResourceRecord) -> dict:
        if row.generation_state != "active_generation":
            raise RuntimeError("current inventory list cannot include historical generation")
        return cls._base(row)

    @classmethod
    def _detail_item(cls, row: ResourceRecord) -> dict:
        item = cls._base(row)
        item["external_references"] = {
            "provider_object_kind": row.provider_object_kind,
            "provider_external_ref": row.provider_external_ref,
        }
        return item
