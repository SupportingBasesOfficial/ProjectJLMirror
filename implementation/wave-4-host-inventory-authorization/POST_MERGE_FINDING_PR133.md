# PR #133 post-merge finding — canonical resource_kind binding

## Finding

A late automated review arrived after PR #133 was squash-merged and identified a material ambiguity: the accepted Monitoring domain/API contract requires `monitoring_resource.resource_kind`, while the host-inventory authorization fixed provider-object identity and future device classification without explicitly binding the canonical `resource_kind` value.

## Severity

P1 — implementation-blocking semantic ambiguity.

## Remediation

For the initial accepted Zabbix host-inventory slice:

```text
provider_object_kind = zabbix_host
monitoring_resource.resource_kind = host
```

`resource_kind=host` is a broad canonical Monitoring resource class only. It is not a declaration that the actual device is a server and it is not the future device taxonomy.

Future classification such as server, switch, router, firewall, access point, VM, storage or appliance remains separately governed and may enrich the same `monitoring_resource_id` without changing its identity.

## Gate

Host-inventory implementation remains blocked until this clarification is canonical through a separately reviewed and authorized merge.
