# Security Requirements

**Status:** proposed baseline

## Identity and credentials

**SEC-ID-001** — Human and machine credentials SHALL be independently revocable and SHALL have explicit expiration/lifecycle policy where applicable.

**SEC-ID-002** — Privileged human access SHALL support MFA and policy-driven step-up/re-authentication where risk warrants it.

**SEC-ID-003** — Password-equivalent secrets SHALL be stored using algorithms/settings appropriate to their credential class; reversible encryption is not a substitute for password hashing.

## Tenant isolation

**SEC-TEN-001** — Tenant context SHALL be resolved from trusted logical identity and platform metadata. Caller-supplied physical schema, database URL, cluster or unrestricted secret reference SHALL NOT select tenant placement.

**SEC-TEN-002** — Tenant isolation SHALL be enforced through multiple layers appropriate to the accepted data architecture, including application authorization and data-layer controls.

**SEC-TEN-003** — Cache keys, pub/sub topics, queue routing, observability dimensions, exports and read models containing protected tenant state SHALL include unambiguous tenant isolation semantics.

## Authorization

**SEC-AUTHZ-001** — Every privileged or protected operation SHALL declare required authorization policy/permission and scope.

**SEC-AUTHZ-002** — Cross-tenant operations SHALL be distinct privileged operations rather than implicit wildcard behavior.

**SEC-AUTHZ-003** — Authorization decisions SHOULD be explainable enough for audit/debugging without exposing secrets.

**SEC-AUTHZ-004** — Tenant-level, whole-cell or other point-in-time recovery SHALL NOT implicitly reactivate authority that was revoked after the selected recovery point. Session/credential revocation, membership disablement/revocation, permission/scope removal, tenant suspension/access denial and equivalent deny state SHALL survive or be reconciled forward before protected traffic resumes.

**SEC-AUTHZ-005** — Authorization/session generation, revocation tombstone or equivalent freshness state used to reject stale authority SHALL NOT move backwards as an incidental effect of business/domain or infrastructure recovery. If post-recovery authorization freshness cannot be established safely, protected admission SHALL fail closed. Reversing a preserved revocation requires a distinct currently authorized and audited security operation.

**SEC-AUTHZ-006** — A recovered tenant, cell or other authority scope SHALL remain non-authoritative for protected/effectful traffic until applicable post-recovery-point security-authority, reliability/accountability, governance and external-effect continuity has been reconciled through the accepted recovery boundary. Recovery uncertainty SHALL NOT be converted into authorization, data re-exposure or retry eligibility.

## Browser and realtime

**SEC-BROWSER-001** — The first-party browser SHALL use the BFF as the confidential session boundary and SHALL NOT receive long-lived platform access or refresh credentials.

**SEC-BROWSER-002** — A protected first-party browser WebSocket SHALL validate the allowlisted expected browser Origin, required short-lived BFF-minted connection capability **and current authorization for the capability scope before the WebSocket upgrade is accepted**. Invalid/null/untrusted Origin, invalid/replayed/expired/wrong-scope capability, revoked/stale underlying authority, or ambient cookie alone SHALL be rejected during the HTTP handshake and SHALL NOT create a retained protected socket.

**SEC-BROWSER-003** — Realtime connection capabilities SHALL be bounded in lifetime and scope, resistant to replay/reuse as appropriate to their contract, and SHALL NOT become general API bearer credentials. For single-use capabilities, replay resistance SHALL use a shared atomic single-winner consume/claim operation before `101`; a read-only or replica-local unused-state check is insufficient. Concurrent presentations across gateway replicas SHALL yield at most one successful consume and at most one protected upgrade.

**SEC-BROWSER-004** — A realtime connection capability SHALL NOT freeze session, membership, permission or tenant-access authority until its expiration. Pre-upgrade admission SHALL prove that the underlying authority remains current using a fresh authoritative decision or a trusted current authorization/session generation/revocation marker. If freshness cannot be established safely, new protected socket admission SHALL fail closed.

**SEC-BROWSER-005** — Capability replay-consumption authority SHALL fail closed when unavailable or unable to prove the accepted use bound. If a single-use capability is atomically consumed but the winning gateway fails before completing the upgrade, that capability SHALL remain consumed and require reminting; recovery from an ambiguous handshake SHALL NOT reopen replay eligibility.

**SEC-BROWSER-006** — Replay-authority restart, loss, restore or reinitialization SHALL NOT make a previously consumed still-valid capability redeemable. Missing replay state SHALL NOT mean unused. The accepted design SHALL either retain/reconcile registered capability/consumption state through the capability validity safety window or bind capabilities to a trusted replay epoch/generation that is advanced before admission resumes after state loss, invalidating outstanding capabilities from the lost epoch. If continuity/current epoch cannot be established safely, protected admission SHALL remain fail closed.

## Secrets

**SEC-SEC-001** — Source code and ordinary configuration SHALL use secret references rather than production secret values.

**SEC-SEC-002** — Secrets SHALL be excluded from application logs, traces, metrics labels, error responses, domain/integration events, queue payloads and audit snapshots.

**SEC-SEC-003** — Secret rotation SHALL be possible without redefining the business entity that references the secret.

## Input and integrations

**SEC-INT-001** — All inbound external data is untrusted and SHALL be validated for schema, size and semantic constraints before entering owning domains.

**SEC-INT-002** — Outbound HTTP/integration capability SHALL defend against SSRF, unrestricted redirects, unsafe protocols/addresses and unbounded response bodies according to connector threat model.

**SEC-INT-003** — Webhook authentication/signature mechanisms SHALL support replay protection where the external protocol allows it.

**SEC-INT-004** — Inbound callback endpoints SHALL enforce a hard transport/raw-body byte limit before buffering the complete body or performing signature/authentication work. Declared `Content-Length` MAY enable earlier rejection but SHALL NOT be the only limit; streaming byte accounting or an equivalent transport-enforced bound SHALL reject oversized bodies. Parser/decompression limits remain independently bounded after authenticity checks.

## Automation and data administration

**SEC-EXEC-001** — Script/command execution SHALL use an execution boundary with explicit target scope, timeout, resource controls, credential context and result/output policy.

**SEC-EXEC-002** — Direct SQL/data administration SHALL use dedicated database/runtime privileges and SHALL NOT run as database superuser or unrestricted application owner.

**SEC-EXEC-003** — Export/import SHALL validate authorization when the request/process is created and again immediately before delayed/asynchronous protected execution. Delayed exports/reports SHALL additionally reauthorize before release/download. A delayed import SHALL NOT mutate tenant data solely because the requester was authorized when the job was queued; workers SHALL re-establish current tenant context and current membership/permission/scope before protected mutation, and stale persisted human authority SHALL NOT be treated as continuing authorization.

**SEC-EXEC-004** — Caller-authored SQL SHALL NOT be allowed to replace the tenant-binding input trusted by RLS/data policy. Interactive SQL against pooled protected data SHALL use a tenant binding the SQL principal cannot alter (for example a tenant-bound database principal/protected mapping) or a mediated/physically isolated query surface with equivalent guarantees.

## Audit and telemetry

**SEC-AUD-001** — Privileged security-sensitive mutations SHALL generate tamper-resistant audit records not mutable by normal application runtime.

**SEC-AUD-002** — Security telemetry SHALL preserve correlation and actor/tenant context without leaking protected values.

**SEC-AUD-003** — When audit evidence is required for a successful local authoritative mutation, the audit record or a durable audit intent SHALL commit atomically with that mutation. Post-commit best-effort audit alone is insufficient.

**SEC-AUD-004** — When the final audit sink is external, the atomically committed audit-intent evidence payload SHALL be append-only/protected from update or delete by normal application and dispatcher roles. Mutable delivery/retry metadata SHALL be segregated from immutable accountability evidence and governed retention/deletion SHALL require separate administrative authority.

## Data governance and recovery

**SEC-GOV-001** — A point-in-time recovery SHALL NOT implicitly reverse a governed deletion/erasure, anonymization/pseudonymization or approved cryptographic-erasure decision that became effective after the selected recovery point. Durable tombstone/decision evidence required to prevent erased or de-identified protected data from becoming authoritative again SHALL survive or be reconciled forward before recovered data is exposed.

**SEC-GOV-002** — Current legal-retention/legal-hold state that constrains deletion, transformation, release or retention SHALL survive or be reconstructed across recovery before destructive lifecycle actions resume. Applicable post-recovery-point hold placement or release decisions SHALL be reconciled from current authoritative governance state rather than inferred from the restored snapshot.

**SEC-GOV-003** — If post-recovery erasure/anonymization status cannot be established safely, affected protected data SHALL remain unavailable rather than be re-exposed. If legal-retention status cannot be established safely, destructive deletion SHALL remain blocked. Recovery uncertainty SHALL NOT be resolved by silently choosing the stale governance state at the recovery point.

**SEC-GOV-004** — Recovery SHALL NOT restore or recreate an older usable cryptographic key path when the current governed intent is approved cryptographic erasure of the corresponding retained ciphertext. Erasure decision/evidence is continuity state even when the erased key material itself is intentionally unrecoverable.

**SEC-GOV-005** — Protected artifact bytes stored outside transactional metadata SHALL use a stable tenant/artifact identity and a staged/reconcilable lifecycle. Bytes SHALL NOT become releasable merely because an object upload succeeded; only verified terminal-ready metadata may authorize release. Crash/recovery/orphan cleanup SHALL remain discoverable and subject to current erasure, retention and legal-hold policy so protected object data cannot become indefinitely untracked or be destructively removed under stale governance.

**SEC-GOV-006** — Governed artifact deletion/erasure SHALL fence both publication and delivery authority. Before an artifact is treated as non-releasable/erased, outstanding download capabilities from an older artifact delivery/lifecycle generation SHALL be revoked or rendered unusable through an application-mediated current-state check, revocable object/access generation or equivalent control. A direct capability that remains usable solely until its original expiry despite current governed erasure is not sufficient for an artifact whose policy requires prompt revocation. Confirmed erasure SHALL NOT be recorded while a known or materially uncertain older delivery capability can still release the protected bytes.

**SEC-GOV-007** — Capability redemption SHALL NOT permanently authorize an artifact stream. Protected artifact delivery that may overlap governed erasure SHALL use generation-bound active delivery lease/stream state or an equivalent stream-level fence. When erasure retires the delivery generation, already-active older-generation streams SHALL be aborted, fenced or deterministically drained and their terminal state SHALL be observable before the artifact is declared fully non-releasable or erasure is confirmed. A mechanism that revokes only future capability presentations while an already-authorized stream can continue releasing protected bytes is insufficient.

**SEC-GOV-008** — Destructive artifact/object cleanup SHALL be serialized with legal-retention/legal-hold state. The destructive path SHALL carry an expected monotonic governance/retention generation or equivalent fencing authority and SHALL prove immediately at the irreversible delete/crypto-erasure boundary that the generation is still current and no effective hold prohibits deletion. Hold placement/release and deletion SHALL share a logical serialization mechanism so a governance mutation that wins the boundary invalidates stale deletion authority. A read-then-delete check-then-act sequence is insufficient; if the implementation cannot prove stale-delete rejection, destructive cleanup SHALL fail closed or remain reconciliation-required.

**SEC-GOV-009** — Active artifact delivery lease admission SHALL be serialized with artifact delivery-generation retirement. Before the first protected byte is released, lease creation SHALL atomically verify a currently releasable artifact state, open delivery admission and the expected current `delivery_generation` while persisting the lease under the same logical authority that erasure uses to close admission/advance the generation. A read-current-generation followed by an unprotected later lease insert is prohibited. If erasure fencing wins the race, stale lease creation SHALL fail and zero protected bytes may be released; if lease admission wins first, the committed lease SHALL be included in the erasure abort/drain set before full non-releasability or confirmed erasure.

## Abuse protection

**SEC-ABUSE-001** — Rate/usage limits SHALL be enforceable across dimensions including principal/API key, tenant, route/operation and integration where required.

**SEC-ABUSE-002** — Expensive capabilities such as reports, exports, imports, SQL queries, automation and provider synchronization SHALL have explicit resource/concurrency controls.

## Supply chain and deployment

**SEC-SUPPLY-001** — Dependencies, build inputs, secrets and release artifacts SHALL be subject to automated integrity/security checks before production release.

**SEC-SUPPLY-002** — Production runtime principals SHALL use least privilege and SHALL be distinct from migration/administrative owners where applicable.