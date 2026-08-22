# Phase 12 — Telemetry Security, Cardinality and Retention

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE  
**Primary upstream authority:** accepted Security Requirements, ADR-014, Data Architecture, Phase 09 URL/error rules, Phase 10/11 security and recovery contracts

## Purpose

Operational telemetry is a high-propagation data plane. This document defines minimization, tenant isolation, redaction, query/access, cardinality, sampling and retention properties that prevent observability from becoming a disclosure, oracle, outage or runaway-cost surface.

## Classification at source

Every stable signal/profile declares the classification of each field family before emission. Producers SHALL prefer semantic safe fields over emitting raw objects and attempting cleanup later.

Secrets/credentials SHALL NOT be emitted into ordinary telemetry at all. Redaction is defense in depth, not permission to log a secret first.

## Prohibited ordinary telemetry content

Ordinary logs/metrics/traces/events SHALL NOT include:

- passwords, access/refresh tokens, API keys, private keys, session cookies or secret values;
- raw Authorization/Cookie headers;
- one-time capabilities or unredacted secret-delivery payloads;
- raw protected cursor payloads;
- raw confidential/restricted URL query strings or filters;
- complete provider/request/response bodies by default;
- domain/integration event payload dumps by default;
- caller-authored SQL or script content by default when it may contain protected data;
- arbitrary object serialization of user/tenant/resource state.

Where diagnostic value requires protected content, a separately governed bounded diagnostic artifact/profile is required; ordinary telemetry is not the escape hatch.

## Field handling classes

Phase 12 uses handling properties rather than inventing a new enterprise data-classification taxonomy:

- **safe_dimension** — bounded value admitted to metric/health dimensions;
- **diagnostic_identifier** — potentially high-cardinality opaque identity usable in logs/traces under access/retention controls;
- **diagnostic_payload** — bounded content requiring stronger minimization/redaction and generally excluded from metrics labels;
- **prohibited_secret** — never ordinary telemetry;
- **accountability_reference** — safe reference to audit evidence, not a copy of the audit record.

Each maps to accepted Security/Data classification rules.

## Tenant isolation

Tenant context is derived from trusted platform state. Observability indexing/query authorization SHALL prevent cross-tenant disclosure.

A tenant identifier in a trace/log does not authorize access to the corresponding tenant telemetry. Query authorization is independent current authority.

Cross-tenant/global operational views are privileged capabilities with explicit safe aggregation and audit where required.

## Metric cardinality

Metric dimensions SHALL be bounded by profile. High-cardinality values such as request IDs, trace IDs, message IDs, resource IDs, arbitrary URLs, error text and provider payload values are prohibited as ordinary metric labels unless an explicit bounded mapping proves otherwise.

Tenant ID as a metric label requires a reviewed need and tenant-cardinality/cost envelope. Platform-wide metrics SHOULD prefer bounded cohorts/classes when individual tenant identity is unnecessary.

## Trace/log cardinality

High-cardinality diagnostic identifiers MAY exist in logs/traces when they are necessary for reconstruction, but volume/indexing policies remain bounded. Searchability does not imply every field must be indexed.

Untrusted values cannot select index/label names or create arbitrary schema fields.

## Duplicate/equivalence evidence privacy boundary

Observability for duplicate-sensitive inbox/replay behavior SHALL expose only bounded outcome and dependency-state classes needed for diagnosis.

Ordinary telemetry SHALL NOT expose protected comparison evidence, comparison-derived equality tokens, or any value that would let an observer test whether protected content in another tenant/consumer scope is equal.

The following are fixed:

- `message_id` is not a metric label and does not become an equality oracle;
- comparison profile/version and historical verifier-generation references, when operationally required, are protected diagnostic identifiers and not public/cross-scope lookup keys;
- comparison success/failure is emitted as a bounded class, not as the compared value;
- tenant/consumer scope is enforced by telemetry query authorization independently of any diagnostic identifier;
- no dashboard/query/export endpoint may provide generic cross-scope “find equivalent message/content” behavior;
- source data confidentiality continues to govern derived observability even when the derived form appears opaque;
- comparison/KMS-equivalent work metrics use bounded profile/workload classes rather than attacker-controlled content/message dimensions.

A low-entropy confidential source does not become safe for cross-scope observability merely because a derived representation is non-human-readable.

## URL and HTTP handling

Signals use normalized route templates and safe parameter-name/classification metadata rather than raw protected URLs/query strings. Response error `instance`, redirect/link values and request headers follow the accepted Phase 09 safe representation rules.

## Sampling

Sampling is signal/profile-specific. It SHALL NOT:

- remove mandatory audit evidence;
- alter customer-monitoring durable-acceptance semantics;
- make SLI denominator/numerator unknowable without the SLI declaring sampling correction/bias;
- systematically hide security/recovery/ambiguous-effect terminal evidence that a required diagnostic profile depends on;
- be controlled by untrusted tenant/provider input to evade observation or increase cost;
- systematically suppress the bounded outcome classes needed to distinguish temporary comparison dependency outage, historical continuity loss and compromised comparison trust.

Head/tail/adaptive sampling mechanisms remain implementation OPEN. Required semantic outcomes do not.

## Retention

Retention duration numerics remain OPEN by signal class until Product/security/compliance/incident/cost evidence exists.

Every profile nevertheless declares:

- retention owner/class;
- minimum evidence dependencies that must not be destroyed prematurely;
- deletion/expiry authority;
- legal-hold/governance interaction where applicable;
- whether a derived/aggregated form may outlive raw telemetry;
- recovery implications.

Audit retention remains owned separately. Observability retention SHALL NOT accidentally become the only copy of evidence required for recovery/accountability.

For comparison diagnostics, observability retention SHALL NOT be relied on as the authoritative historical comparison-proof horizon. Expiring observability cannot grant duplicate/replay eligibility, and longer observability retention cannot recreate retired comparison authority.

## Redaction and transformation

Redaction/minimization occurs as early as practical and is repeated at sinks/query/export boundaries where useful. Redaction failures are release-blocking for protected fields.

Hashing a low-entropy confidential value is not automatically safe anonymization. Tokenization/keyed transformation requires threat/privacy review and must not create a cross-tenant correlation oracle.

## Query/export access

Telemetry query/export capabilities are protected operations. They require current authorization and bounded scope. Export paths reapply classification/redaction rules and SHALL NOT turn a privileged internal index into an unrestricted download.

Provider/support access, if ever allowed, is separate privileged authority and not implied by observability backend administration.

## Restore/recovery

Restored observability data SHALL NOT re-expose content whose current governed state requires erasure/anonymization where the accepted recovery model applies. Missing telemetry after restore is not proof an event/effect did not occur.

Observability backends do not become recovery truth merely because their retention is longer than transactional state.

Stale restored comparison-health telemetry SHALL NOT establish current verifier/profile continuity or duplicate/replay eligibility. Current owning authority and recovery evidence remain mandatory.

## Validation obligations

Automated/adversarial tests SHALL cover secret-pattern leakage, raw URL/query leakage, cross-tenant query attempts, label/cardinality explosion, untrusted schema-field creation, sampling evasion/amplification, retention expiry, restored stale telemetry and privileged export boundaries.

Duplicate-sensitive tests SHALL additionally attempt cross-tenant/cross-consumer equality inference through metrics, logs, traces, dashboards and exports and SHALL prove that only bounded non-oracle outcome classes are observable.
