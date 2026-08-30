# D3 Candidate Matrix — bounded evidence inputs

**Recorded:** 2026-08-30  
**Authority:** evidence input only; `state-manifest.json` remains the machine-owned D3 state  
**Rule:** candidate selection here does not grant canonical Product implementation or production authority.

## Selection criteria

Candidates are evaluated against fixed JLMirror contracts using:

1. standards alignment and protocol interoperability;
2. multi-year project/governance health and security maintenance;
3. portable deployment across cloud/on-prem/runtime classes;
4. ability to sit behind narrow JLMirror ports/adapters;
5. deterministic failure/recovery/concurrency testability;
6. license/governance risk and feasible substitution path;
7. operational complexity proportional to the authority actually owned.

Popularity is supporting evidence, never architectural authority.

## D3-A — human IdP

**Primary evidence candidate:** Keycloak `26.7.2`.

Rationale:

- existing `IR-D-001-keycloak-idp-decision-record.md` already selects Keycloak as the candidate human IdP;
- Keycloak 26.7.2 was released 2026-08-19 and supersedes 26.7.0/26.7.1 with current security fixes, so D3 security evidence must target the current maintained patch rather than carry forward evidence from a superseded patch;
- current Keycloak documentation/release history supports OIDC Back-Channel Logout; the D3 harness must prove the exact JLMirror profile rather than trust feature presence;
- Keycloak remains behind the JLMirror OIDC/BFF boundary; realm/group/organization objects are forbidden from becoming JLMirror authorization truth;
- prior 26.7.0 exploratory evidence is historical only and is not credited to the 26.7.2 candidate until the digest-pinned exact-HEAD harness passes.

External evidence references:

- https://www.keycloak.org/2026/08/keycloak-2672-released
- https://www.keycloak.org/downloads
- https://www.keycloak.org/docs/latest/release_notes/

## D3-B — session durable authority + security acceleration cache

**Durable authority candidate:** PostgreSQL `18.6`.  
**Primary cache candidate inherited from OPEN-REL-031:** Redis-compatible security-cache mechanism.  
**Portability control candidate:** Valkey `9.1`.

Rationale:

- PostgreSQL is already the selected candidate Identity/session SoR and is current business/authority truth technology in JLMirror; PostgreSQL 18.6 was released 2026-08-13;
- the record names Redis as the cache candidate, but D3 shall test the security-cache contract through a narrow port rather than expose product-native identity;
- Redis 8 has an AGPLv3 option but also RSALv2/SSPLv1 licensing choices; this history is a governance reason not to make a brand-specific command/data model canonical;
- Valkey 9.1, governed under the Linux Foundation, is a useful substitution control for the subset of cache semantics D3 actually requires;
- passing the same authority/fencing vectors against the portability control is evidence that JLMirror depends on semantics, not the vendor name.

This does **not** preselect Valkey over Redis. Final D3-B acceptance shall name the exact accepted cache profile after empirical evidence.

External evidence references:

- https://www.postgresql.org/docs/release/18.6/
- https://redis.io/legal/licenses/
- https://www.linuxfoundation.org/press/valkey-enhances-efficiency-security-and-modular-performance-with-9.1-release-and-new-ecosystem-integrations

## D3-C — CSRF/key rotation

**Primary evidence candidate:** application-owned HMAC-SHA-256 double-submit profile with a versioned two-generation key ring supplied through the D3-E key-authority port.

No browser/framework library becomes authority. The evidence harness tests the accepted token/session-lineage semantics independently of any future frontend framework.

## D3-D — workload identity issuer/attestation

**Primary evidence candidate:** SPIRE `1.15.2`.

Rationale:

- IR-D-002 already fixes SPIFFE-compatible workload URI identity + X.509-SVID-compatible short-lived credentials + mTLS;
- SPIRE is the reference runtime environment for SPIFFE and is a CNCF Graduated workload-identity project;
- release 1.15.2 was published 2026-07-09 and includes current security/attestation maintenance;
- the candidate naturally tests whether JLMirror can keep canonical workload identity independent of pod/node/IP/vendor identity.

External evidence references:

- https://github.com/spiffe/spire/releases/tag/v1.15.2
- https://github.com/spiffe/spire/blob/main/CHANGELOG.md
- https://www.cncf.io/blog/2026/08/07/shadow-ai-in-ci-cd-threat-modeling-the-path-from-developer-laptop-to-kubernetes/

## D3-E — key/replay/historical-verifier authority

**Primary bounded evidence candidate:** OpenBao `2.6.2` Transit behind a provider-neutral `KeyAuthorityPort`.  
**Status:** evidence candidate only; not production-canonical.

Rationale:

- OpenBao Transit exposes HMAC/sign/verify and derived-key/context operations that can exercise D3's cryptographic-domain-separation and generation contracts;
- OpenBao 2.6.2 was released 2026-08-18 with current security fixes;
- OpenBao is presently a CNCF Sandbox project, materially less mature than SPIRE's Graduated status; therefore D3 must not couple canonical semantics to OpenBao-native namespace/path/token concepts;
- the evidence harness must make backend replacement visible by exercising the same `KeyAuthorityPort` contract against a deterministic in-process reference backend as a negative/control implementation where appropriate;
- future HSM/cloud-KMS/PKCS#11 backends remain substitutable if they satisfy the same port and recovery/generation contract.

External evidence references:

- https://openbao.org/community/release-notes/2-6-0/
- https://openbao.org/docs/secrets/transit/
- https://www.cncf.io/blog/2026/08/07/shadow-ai-in-ci-cd-threat-modeling-the-path-from-developer-laptop-to-kubernetes/

## Evidence pinning rule

Executable workflows SHALL pin immutable image digests or otherwise verify downloaded artifact checksums before a candidate result can be promoted from exploratory to canonical conformance evidence. A mutable tag or unverified `latest` result is exploratory only.

## Candidate substitution rule

A candidate may be replaced without reopening D3 semantics only if the replacement proves the same externally visible contracts and failure classes. Any replacement that requires changing tenant identity, session authority, authentication strength, workload identity, replay identity, fencing or cryptographic-domain semantics is a semantic change and reopens the governing decision rather than being classified as a mechanism substitution.
