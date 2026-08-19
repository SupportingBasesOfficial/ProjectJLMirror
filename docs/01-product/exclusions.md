# Product Exclusions and Non-Goals

**Status:** accepted

The following are not product assumptions unless separately accepted by requirement or ADR.

- JLMIRROR is not defined as a skin or replacement UI for one monitoring vendor.
- JLMIRROR does not require every bounded context to be an independently deployed microservice.
- Kubernetes is not a mandatory runtime merely because the product targets enterprise environments.
- A particular queue, cache, event bus, time-series engine, cloud provider, secrets manager, or object store is not a product requirement by default.
- Event sourcing is not a universal persistence model.
- CQRS is not a universal requirement; specialized read models may be used where justified.
- Real-time delivery does not imply exactly-once delivery.
- Feature flags do not grant authorization.
- A global administrator role does not imply unrestricted, unaudited bypass of tenant controls.
- Schema-per-tenant, shared telemetry, database-per-tenant, or dedicated-cluster placement are implementation strategies governed by accepted architecture, not product identity.
- Public status pages, reports, exports, and webhooks do not expose internal database models directly.
- Direct script or SQL execution is not inherently trusted simply because the caller is authenticated.

These exclusions prevent accidental architecture commitments before the corresponding requirements and evidence exist.