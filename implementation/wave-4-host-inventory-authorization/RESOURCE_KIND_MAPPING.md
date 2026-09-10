# Host Inventory canonical resource-kind mapping

For `wave4.monitoring-host-inventory@1`, the mapping is exact:

```text
Zabbix provider object: host
provider_object_kind: zabbix_host
canonical Monitoring resource_kind: host
```

The three concepts are intentionally distinct:

- `monitoring_resource_id` is canonical identity.
- `resource_kind=host` is the broad Monitoring resource class required by the accepted domain/API contract.
- `provider_object_kind=zabbix_host` records provider-native object class/origin.
- future canonical device classification determines what the resource actually is (for example server, switch, router, firewall, VM, storage, appliance) under a separate contract.

No implementation may substitute provider object type or inferred device taxonomy into `resource_kind` for this slice.
