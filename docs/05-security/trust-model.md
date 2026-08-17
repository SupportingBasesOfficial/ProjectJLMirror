# Security and Trust Model

**Status:** proposed baseline

## Security posture

JLMIRROR assumes the network is not a trust boundary by itself. Trust is established per interaction using authenticated principal identity, validated tenant context, authorization, controlled credentials, data-layer restrictions, and audit where applicable.

## Primary trust boundaries

1. Internet -> Web/BFF
2. Web/BFF -> API
3. API -> domain/application boundary
4. Application -> database/cache/queue
5. Queue -> worker
6. Worker -> privileged execution environment
7. Platform -> external provider
8. External provider -> inbound webhook/connector
9. Tenant administration -> privileged tenant operations
10. Platform administration -> cross-tenant control plane
11. SQL/data-administration tools -> data plane
12. Export/public status/reporting -> external information release

## Threat classes that must be explicitly modeled

- cross-tenant data disclosure or mutation;
- privilege escalation from viewer/operator/tenant admin to stronger scopes;
- confused-deputy behavior in workers and background jobs;
- forged or replayed asynchronous messages;
- credential/session theft and refresh-token abuse;
- cache-key or pub/sub-channel tenant collisions;
- SSRF and outbound request abuse through webhooks/connectors;
- malicious or malformed monitoring-provider payloads;
- unsafe script execution and target expansion;
- SQL console privilege escalation;
- data exfiltration through exports, reports, logs, errors, webhooks, or marketplace integrations;
- secret leakage through telemetry;
- compromised external provider attempting lateral movement;
- migration or tenant-placement mistakes causing cross-tenant access.

## Authorization

Authentication answers who the principal is. Authorization answers what the principal may do in a specific scope. Tenant membership, roles, permissions and resource scope are separate concepts.

## Cross-tenant administration

Cross-tenant actions are exceptional privileged operations, not an implicit property of a global account. They require explicit authorization context, narrow operation scope, and audit attribution.

## Asynchronous trust

A queue message is not inherently trusted because it originated inside the platform. Workers validate message version, required logical identifiers, job authorization policy where applicable, and resolve physical tenant placement from trusted platform metadata.

## External trust

All external providers are treated as potentially unavailable, slow, malformed, compromised, or semantically inconsistent. Adapters validate, normalize, constrain timeouts/retries, and prevent provider-native identifiers or payloads from becoming unrestricted internal authority.