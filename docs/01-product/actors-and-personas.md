# Actors and Personas

**Status:** accepted

## Human actors

### Platform Administrator
Operates JLMIRROR at platform scope. Manages tenants, global configuration, placement, platform catalog, customer/commercial metadata, and explicitly authorized cross-tenant administration. Cross-tenant access is privileged and auditable.

### Tenant Administrator
Administrates one tenant. Manages tenant memberships, roles, integrations, policy/configuration, branding, and tenant-level privileged operations.

### Tenant Operator
Operates infrastructure and service workflows for a tenant. Typical responsibilities include monitoring, incident/ticket handling, approved automation, changes, and operational response.

### Tenant Viewer
Consumes authorized read-only operational, SLA, status, and reporting information.

### Auditor / Compliance Operator
Reviews evidence, audit history, compliance controls, security posture, and governed data actions within an authorized scope. This may be represented by a custom role rather than a hard-coded system role.

## Machine actors

### API Principal
A non-human principal authenticated through an API credential or equivalent mechanism and constrained by tenant, permissions, scopes, revocation, and rate limits.

### Worker Principal
A trusted internal runtime principal executing asynchronous jobs. A worker does not infer tenant placement from untrusted payload fields; it resolves tenant context through trusted platform metadata.

### External Provider
An external service such as monitoring, ITSM, identity, notification, payment, or infrastructure provider. External providers are untrusted boundaries and are accessed through adapters.

### Webhook Consumer
An external destination receiving versioned integration events. Delivery is retriable, observable, auditable, and isolated from the originating transaction.

## Authorization model note

Named personas describe defaults, not the full authorization model. The canonical model supports memberships, roles, permissions, custom roles, and resource/scope refinement.