# Runtime Topology

**Status:** proposed

## Global request path

```text
Internet
  |
CDN / WAF / Edge Routing
  |
+------------------------------+
|                              |
Web/BFF                    Direct API clients
|                              |
+--------------+---------------+
               |
      Authenticated API ingress
               |
      Logical Tenant Resolution
               |
         Cell Routing Layer
               |
       +-------+-------+
       |               |
     Cell A          Cell B ... N
       |               |
  API replicas      API replicas
  Worker pools      Worker pools
  Data plane        Data plane
```

## Cell internals

```text
                   Cell
                    |
        +-----------+-----------+
        |                       |
   API Runtime              Worker Runtime
        |                       |
  Domain Modules          workload classes
        |                       |
        +-----------+-----------+
                    |
          Transactional Store
                    |
       +------------+------------+
       |             |            |
   Outbox/Jobs    Telemetry    Object artifacts
       |             |            |
       +-------------+------------+
                    |
             Observability export
```

## Runtime rules

1. API replicas are stateless except for bounded in-process caches that are never authoritative.
2. Durable state lives in accepted data/storage systems, not process memory.
3. Worker classes scale independently by workload/queue lag and have explicit concurrency limits.
4. Script/command execution is not hosted inside the primary API process.
5. External providers are accessed through connector/adapters with timeout, egress and circuit policies.
6. Cell routing uses logical tenant identity and trusted placement metadata; clients cannot choose a database/cluster.
7. The control plane is authoritative for placement but SHOULD NOT require a synchronous remote lookup on every ordinary data-plane request. Safe last-known-good/versioned placement caching is allowed by policy.
8. A cell rejects work whose tenant placement/version is not admitted to that cell.
9. Public status/report/export surfaces consume deliberate projections/artifacts rather than exposing operational tables.
10. Core API/worker execution uses general-purpose runtimes; edge runtimes are optional acceleration/composition layers.

## Failure containment

The normal failure boundaries are:

- tenant external-provider dependency;
- destination/integration;
- worker workload class;
- data-plane cell;
- control-plane capability;
- web delivery layer.

A failure in one boundary should degrade only capabilities that depend on it unless the failed component is an explicitly critical shared dependency.
