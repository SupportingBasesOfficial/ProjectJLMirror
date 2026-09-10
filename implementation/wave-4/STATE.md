# Wave 4 — Zabbix initial validation worker state

Current bounded implementation: `wave4.zabbix-initial-validation-worker@1`.

Canonical predecessor: `main@d642a7f456e042dd02de2c04533c39c748f88aa9`. Implementation authority remains `wave4.monitoring-zabbix.vertical@1`; ADR-022 remains a compatibility constraint rather than a new runtime grant.

## Product behavior implemented

After a Monitoring Source is created locally, its durable `validation_and_initial_sync` operation may be claimed exactly once by this bounded worker. The worker resolves the configured credential through an abstract secret boundary, obtains fail-closed outbound admission for the currently bound Zabbix base URL, and performs only `hostgroup.get` for the configured HostGroup references.

A successful validation means every configured HostGroup anchor is currently visible through the admitted endpoint under the resolved integration identity. The source becomes `current` and the operation becomes `succeeded`.

A missing configured HostGroup, including loss of visibility to one of the configured anchors, produces `incomplete` + `reconciliation_required`. A missing configured HostGroup does not mean all monitored resources disappeared and MUST NOT authorize mass negative inference.

Credential resolution failure, provider authentication rejection, provider unavailability, unsafe/unprovable egress, or invalid provider protocol evidence produces `unavailable` + `reconciliation_required`. Existing source identity and any historical monitoring data are not deleted or rewritten by these outcomes.

## Fencing

The claim snapshots source-instance generation plus configuration and scope revisions. Completion is accepted only if generation, configuration revision, scope revision, provider-scope tenant binding and provider-instance lineage are still current. An in-flight response from stale authority cannot update current source evidence.

The worker does not derive physical-provider ownership or replacement from Zabbix numeric IDs. Zabbix does not provide a trusted provider installation self-identity primitive for this purpose; the governed `provider_instance_ref + provider_base_url + source_instance_generation` lineage remains platform authority, and base-URL changes still require ADR-021 replacement flow.

## Secret and network boundaries

The API token exists only as in-memory secret material returned by `CredentialResolver`; this slice does not select or implement the concrete secret manager. Outbound DNS/IP/protocol/redirect/egress enforcement remains behind `OutboundAdmission`; this slice does not select a concrete egress transport or weaken the fail-closed requirement.

No automatic retry cadence is selected here. A failed/degraded initial validation becomes durable `reconciliation_required`; retry scheduling remains separately governed because exact cadence/capacity numerics remain OPEN.

## Deliberately not implemented

No host inventory ingestion, resource canonicalization, metric/item/history ingestion, problem ingestion, current-state polling, webhook path, HTTP adapter, frontend, ProviderInstance registry runtime, Organization/Commercial runtime, provider write-back or production/C3 numerics are implemented in this slice.

The next bounded product behavior to validate before implementation is `host.get` inventory ingestion and the exact rules for creating/updating/retiring canonical monitoring resources without turning provider uncertainty into absence.
