# Implementation Readiness — Implementation Conformance & Blocker Register

**Status:** proposed gate baseline; post-D2 operational state reconciled by `18-d2-track-b-acceptance-propagation.md`

## Global implementation blockers

Implementation authorization SHALL NOT be issued while any applicable condition is true:

1. a required C1 OPEN remains unresolved;
2. an implementation slice lacks accepted Product/Requirement authority;
3. a slice lacks exact API/event/profile IDs and owner joins;
4. framework/vendor behavior is proposed as canonical semantics without governance;
5. tenant/current authorization can be inferred from physical/network/provider/workload identity alone;
6. protected effect paths lack stable identity/idempotency/fencing/reconciliation where required;
7. recovery/restore can regress current authority or interpret missing state as absence;
8. Product-gated/deferred capability can appear through configuration/defaults;
9. implementation chooses C3 production numerics and represents them as accepted targets without evidence;
10. release/build/supply-chain path can promote code before Phase 14 authority is implemented;
11. slice tests omit applicable adversarial/fault vectors;
12. implementation evidence cannot distinguish L1/L2/L3/L4 provenance;
13. AI/tool output can grant/deny protected action eligibility;
14. deterministic assurance is absent on exact implementation HEAD;
15. an implementation PR changes normative architecture to fit code without an owning governance change;
16. a privileged human operation can treat valid login/session/role as sufficient when current Security policy requires stronger MFA/step-up/re-authentication assurance;
17. machine client authentication accepts replayed `private_key_jwt` assertions or a retired client-key generation;
18. replay-sensitive machine authentication uses replica-local/check-then-insert state, issues while replay authority cannot prove unused-state, or treats replay-state loss/restore as proof that an assertion is unused.

## Slice-specific blockers

### `impl.identity-bff@1`

Blocked unless IR-D-001/002 are accepted and the implementation preserves:

- BFF confidential token handling and browser exclusion from long-lived platform credentials;
- exact OIDC `state` + PKCE S256 + per-transaction `nonce` binding and issuer/audience/client checks;
- current authorization/tenant membership independent from token/session validity;
- policy-driven MFA/step-up/re-authentication currentness for privileged operations using trusted authentication-assurance evidence;
- asymmetric machine authentication with unique-`jti` replay rejection and current client-key generation;
- one logical cross-replica machine-assertion replay authority with atomic single-winner admission, fail-closed outage/partition behavior and restore continuity;
- internal workload/service mTLS identity kept separate from tenant/domain authorization;
- Phase 09 CSRF/Origin contracts.

`IRV-008..012` and `IRV-031..033` are mandatory identity-slice falsification anchors.

### `impl.control-plane@1` / `impl.cell-data-runtime@1`

Blocked unless IR-D-002/003 are accepted and placement/runtime/config/credential/network generations remain distinct and fenced.

### `impl.async-core@1`

Blocked until a C2 transport/equivalence/outbox/inbox mechanism is selected through governed evidence. The selection cannot weaken Phase 10/11 semantics.

### `impl.provider-integration@1`

Each provider adapter is independently blocked until Product/domain authority and provider-specific callback/outbound authentication/reconciliation profiles exist.

For the first Monitoring/Zabbix vertical, Track A already supplies the accepted Monitoring domain/API/event and Zabbix trust/normalization contracts. Any remaining concrete credential/secret/transport mechanism stays governed by its existing C2 owner and by the exact slice authorization scope.

### `impl.realtime@1`

Initially deferred. Blocked until the realtime implementation slice is explicitly activated and its browser presentation/resume C5 decisions are reclassified/closed.

### `impl.customer-telemetry@1`

The former `OPEN-REL-030` evidence blocker is **satisfied for the accepted Track B profile** merged by PR #40 at `main@2ffec007d7dff32e0a45116b0bc875d5c2743b12`.

The slice is therefore `eligible_for_implementation_authorization`, but it remains **not authorized to implement** until a separate Wave 4 implementation-authorization gate grants the exact slice. Implementation must preserve the accepted D2 profile and all joined Product/domain/API/event/security/recovery contracts. `OPEN-REL-020` C3 production capacity/performance/cost envelopes remain production blockers rather than reasons to reinterpret D2 as unlimited.

### `impl.artifact@1`

Internal opaque artifact lifecycle may be implemented when its C2 storage mechanism is selected. Product-facing active-inline/direct-delivery branches remain Product-gated.

### `impl.release-supply-chain@1`

Implementation of CI/build/release automation may begin only through bounded C2 mechanism selection preserving source trust, immutable artifact, release fencing and runtime verification.

### `impl.operations-recovery@1`

Tooling may implement accepted operational records/runbooks but cannot invent staffing/numeric C3 values or make runbook/tool state authoritative.

## Release and production blockers

Implementation readiness does not clear C3 OPENs. A future release/production gate must prove actual runtime evidence, including measured capacity/performance, SLO/RPO/RTO, rollout thresholds, retention, recovery drills, build provenance, incident/on-call readiness and compliance obligations where applicable.

Track B acceptance does not turn production numerics into implementation defaults. Any provisional non-production bounds used to generate evidence must be finite, explicit, non-authoritative and traceable to the owning C3 closure path.

## Branch protection hosting gap

Repository hosting enforcement remains externally tracked. Until `main` is actually protected with required deterministic assurance, operator discipline and explicit expected-head merge checks remain mandatory. The absence of hosting enforcement cannot be represented as resolved by this gate.