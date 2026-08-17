# Ubiquitous Language and Glossary

This glossary defines canonical terminology. Domain-specific refinements may extend it but must not silently redefine these meanings.

- **JLMIRROR:** the platform described by this repository.
- **Platform:** global JLMIRROR capabilities and control-plane functions shared across tenants.
- **Tenant:** a customer organization represented as an isolated administrative and data boundary.
- **Principal:** a human or machine identity attempting an action.
- **Identity:** the persistent representation of a principal and its authentication bindings.
- **Membership:** the relationship between an identity and a tenant.
- **Role:** a named set of permissions assigned within a scope.
- **Permission:** an authorization capability such as reading a resource or approving an operation.
- **Tenant Context:** validated runtime context identifying tenant, principal, authorization scope, and request/job correlation.
- **Control Plane:** global metadata and operations used to manage tenants and the platform.
- **Data Plane:** tenant-scoped operational state and workload processing.
- **Telemetry:** high-volume measurements, logs, traces, or temporal operational observations.
- **Monitoring Source:** an external provider that supplies monitoring information; Zabbix is an initial source, not the definition of the Monitoring domain.
- **Resource:** an infrastructure object represented within JLMIRROR.
- **Observation:** raw or normalized information indicating resource state at a point in time.
- **Problem:** a detected abnormal condition reported or derived from monitoring data.
- **Alert:** an actionable representation of a condition that may require notification, correlation, escalation, automation, or incident creation.
- **Incident:** an operational service-impacting condition managed through an operational lifecycle.
- **Ticket:** an ITSM work record. A ticket is not synonymous with an alert or incident.
- **Job:** a durable instruction for asynchronous work.
- **Domain Event:** a durable statement that a meaningful domain fact occurred.
- **Integration Event:** a versioned event safe for consumption outside the owning boundary.
- **Projection / Read Model:** derived state optimized for a specific read or presentation use case.
- **Audit Event:** an immutable accountability record describing a relevant action and actor.
- **Provider / Adapter:** implementation that connects a stable JLMIRROR port to an external system.
- **Placement:** metadata describing where a tenant workload/data boundary resides.
- **Failure Domain:** a boundary within which a failure should be contained.
- **Degraded Mode:** intentional reduction of capability while preserving unaffected system functions.