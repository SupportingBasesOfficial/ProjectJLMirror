# Implementation Readiness — Security & Privacy Assurance Review

**Status:** proposed gate baseline

## Purpose

This review verifies that implementation can select mechanisms without inventing or weakening Security/Privacy authority.

## Trust boundaries preserved

Every slice SHALL preserve at least the applicable boundaries:

- browser JS -> BFF confidential boundary;
- external principal -> identity authority -> authentication-strength evidence -> current platform authorization;
- workload identity -> service authentication -> application authorization;
- request ingress -> canonical HTTP meaning -> tenant placement -> use case;
- producer/provider -> canonical event/callback meaning -> trusted scope -> domain;
- Control Plane placement authority -> cell/runtime admission;
- runtime/config/credential/network generations -> current authority checks;
- untrusted source -> bounded validation -> accepted source -> privileged release chain;
- backup/restore -> quarantine -> `(R,F]` reconciliation -> recovery admission;
- operational evidence/runbook -> owning protected authority.

## Identity closure review

The C1 profiles in `04-must-close-identity-and-fencing-profiles.md` satisfy readiness only if implementations preserve:

- OIDC Authorization Code + PKCE S256 at the BFF for first-party browser login;
- per-transaction `state` + `nonce` binding and exact callback/token issuer/audience/client validation;
- browser exclusion from long-lived platform credentials;
- policy-driven MFA/step-up/re-authentication currentness for privileged human operations, with trusted assurance evidence such as accepted `acr`/`amr` semantics rather than UI/role/default inference;
- asymmetric attributable machine authentication using replay-resistant `private_key_jwt` assertions with unique `jti`, current key generation and exact token-endpoint audience;
- SPIFFE-compatible short-lived workload identity + mTLS service authentication;
- strict separation between authenticated service identity and tenant/domain authorization;
- environment/trust-domain isolation;
- current issuer/bundle/credential generations and revocation.

A valid login/session/token/certificate is never enough when the current owning policy requires stronger authentication assurance, current authorization, placement or tenant scope.

## Tenant isolation

No implementation slice may derive tenant authority from:

- URL/body/provider fields alone;
- workload/network identity alone;
- broker topic/partition;
- physical database/cell/region;
- observability correlation;
- artifact/storage location;
- incident/operator context.

Tenant context is derived by accepted placement/auth authority and revalidated where the owning contract requires it.

## Secret/key handling

- secrets are references outside the secret authority;
- secret values are excluded from ordinary config/events/jobs/logs/traces/artifacts/audit snapshots;
- machine/workload private keys are not shared credentials;
- key/verifier retirement preserves historical proof where required without reviving current authority;
- restore cannot make revoked/retired credentials current.

## Egress / confused deputy

Provider, webhook, callback, parser, automation and diagnostic paths keep explicit destination/protocol/redirect/DNS/private-network policies. Runtime/vendor reachability never becomes authorization.

## Data classification / privacy

Every implementation slice maps stored/transmitted/evidence fields to accepted classification and minimization rules. Cross-tenant diagnostic/admin surfaces require explicit accepted authority and immutable accountability. Product-gated public/export/inline capabilities remain absent while their upstream selector is OPEN.

## Recovery privacy continuity

Restore/PITR/rollback SHALL NOT regress:

- revocation/deny state;
- authentication-strength/current-policy state used for privileged admission;
- erasure/legal hold;
- cryptographic authority;
- audit/reliability evidence;
- customer-monitoring acceptance/projection currentness;
- artifact lifecycle/disclosure authority;
- placement/runtime/release fences.

## Supply-chain boundary

Untrusted candidate source cannot acquire release/signing/migration/production secrets or choose the policy/runner/token that evaluates its own trust. Runtime artifact/config currentness is verified independently of deployment-controller desired state.

## AI boundary

AI may generate hypotheses, tests, summaries or code drafts. AI output SHALL NOT be direct, indirect, intermediate or joint authority for authentication, authentication-strength/step-up decisions, authorization, tenant/placement authority, Product applicability, retry/redrive/replay/recovery eligibility, incident closure, break-glass, release/merge approval or architecture decisions.

## Security blockers

Implementation authorization is blocked for a slice if any applicable item lacks:

- current principal/credential profile;
- current authentication-strength/step-up policy and trusted evidence path for privileged human operations;
- explicit tenant boundary;
- least-privilege state-port/egress profile;
- secret-reference handling;
- revocation/currentness behavior;
- recovery continuity;
- abuse/SSRF/confused-deputy evidence plan;
- security compatibility classification;
- applicable adversarial tests, including `IRV-031` and `IRV-032` where the identity slice applies.
