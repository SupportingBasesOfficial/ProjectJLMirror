# Capability-Specific Resilience Profiles

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document applies the common Phase 11 semantics to accepted platform capability classes. Endpoint- or Product-specific behavior remains owned by the corresponding accepted contract/profile.

## Canonical profile catalog

This table instantiates every profile referenced by the capability/dependency map. It is a normative, machine-joinable catalog: `reliability_profile_id` plus `profile_version` is the profile key, and each evidence, blocker and OPEN identifier SHALL resolve in the Phase 11 package. Narrative sections below expand these records but SHALL NOT replace or contradict them.

| `reliability_profile_id` | `profile_version` | `owning_capability`; `scope` | `truth_authority`; `dependency_set` | Human-readable failure summary → mode | Isolation and resumption summary | Evidence, blockers and OPENs summary |
|---|---|---|---|---|---|---|
| `rel.control-plane-placement` | `1` | Platform Management; tenant placement/cell lifecycle | Control Plane placement/lifecycle generation; hard: authority store; continuity: deny, placement and recovery generations | unavailable/partitioned → `stale_tolerant` only under bounded lease; stale/identity conflict → `fail_closed`; recovery blocked → `reconciliation_blocked` | Control Plane vs cell and tenant lifecycle; resume after current generation, destination admission and `(R,F]` reconciliation | `FV-CP-001`, `FV-CP-002`, `FV-REL-001`; `RB-REL-001`, `RB-REL-019`; `OPEN-REL-001`, `OPEN-REL-002`, `OPEN-REL-004` |
| `rel.cell-transactional-store` | `1` | Owning cell/application processes; cell/tenant | authoritative transactional store plus co-resident idempotency/inbox/outbox/effect ledgers; hard: writer authority; continuity: recovery generation | unavailable/partitioned → `fail_closed`; slow → `fail_fast`; recovery blocked → `reconciliation_blocked` | cell blast radius and tenant transaction; resume after single current writer fence and recovery gates | `FV-CELL-001`, `FV-CELL-002`, `FV-REC-001`, `FV-REC-002`, `FV-REL-001`; `RB-REL-002`, `RB-REL-003`, `RB-REL-018`, `RB-REL-019`; `OPEN-REL-003`, `OPEN-REL-004`, `OPEN-REL-013` |
| `rel.security-session-authority` | `1` | Security authority; principal/tenant/scope | current authn/authz/revocation/deny generation; hard: verification authority; continuity: revocation and audit | unavailable/stale/compromised → `fail_closed`; policy denied → `capability_unavailable` | principal, tenant and scope; resume only after current non-regressing deny/revocation evidence | `FV-SEC-001`; `RB-REL-004`; `OPEN-REL-026`, `OPEN-REL-027` |
| `rel.placement-reference-cache` | `1` | Platform Management; tenant/cell/generation | bounded signed/versioned copy; authority: Control Plane plus destination admission; optional: cache transport | unavailable → `fail_fast` to authority when safe; stale/identity conflict → `fail_closed`; valid bounded copy → `stale_tolerant` | tenant/generation key and fallback concurrency; resume/refill after freshness and admission proof | `FV-CP-002`, `FV-CACHE-001`; `RB-REL-001`, `RB-REL-005`; `OPEN-REL-001`, `OPEN-REL-002`, `OPEN-REL-015` |
| `rel.performance-cache` | `1` | Owning application capability; tenant/operation | authoritative origin; optional: derived cache | unavailable → `fail_fast` to origin when bounded; stale → `stale_tolerant` only by accepted Product semantics; saturated → `shed_or_reject` | tenant/operation refill bulkhead; resume after origin health and stampede control | `FV-CACHE-001`, `FV-OVER-001`; `RB-REL-005`, `RB-REL-012`; `OPEN-REL-007`, `OPEN-REL-008`, `OPEN-REL-015` |
| `rel.replay-consume-state` | `1` | Owning API/event capability; tenant/capability epoch | consumption/equivalence/dedup authority; hard: transactional ledger; continuity: replay epoch and retention | unavailable/stale/gap → `fail_closed`; identity conflict → `reconciliation_blocked`; permanent invalid → `capability_unavailable` | tenant/source/epoch; resume after continuity proof or trusted epoch invalidation | `FV-ASYNC-003`, `FV-ASYNC-004`, `FV-REC-003`; `RB-REL-010`, `RB-REL-011`, `RB-REL-018`; `OPEN-REL-015`, `OPEN-REL-025` |
| `rel.secret-key-authority` | `1` | Security/cryptographic authority; runtime/cell/tenant/namespace | current secret/key generation and lease; hard: secret/KMS authority; continuity: rotation, revocation and crypto-erasure | unavailable → `capability_unavailable`; stale/compromised/governance blocked → `fail_closed` | secret namespace and least-privilege runtime identity; resume after current authority and rotation/erasure state | `FV-SECRET-001`; `RB-REL-006`; `OPEN-REL-016` |
| `rel.configuration-authority` | `1` | Configuration-owning capability with Platform Management distribution; tenant/cell/runtime-role/config scope | accepted schema-valid configuration content, applicability and generation; hard: configuration authority; continuity: rollout/restore ledger | unavailable → bounded `stale_tolerant` only for verified last-known-good; malformed/contradictory/partial/stale → `fail_closed`; recovery blocked → `reconciliation_blocked` | tenant/cell/role/config namespace and rollout generation; resume after one accepted generation, target coverage and recovery disposition | `FV-CONFIG-001`, `FV-CONFIG-002`; `RB-REL-023`; `OPEN-REL-029` |
| `rel.outbox-publication` | `1` | Owning transactional process and dispatcher; cell/producer/contract | atomic business fact plus immutable outbox intent; hard: cell store; async: broker; continuity: source/message generation | broker unavailable/throttled → `queued_or_deferred`; identity conflict → `reconciliation_blocked`; saturated → `shed_or_reject` admission before commit | cell/producer/contract backlog; resume same message identity after durable intent reconciliation | `FV-ASYNC-001`; `RB-REL-009`; `OPEN-REL-012`, `OPEN-REL-025` |
| `rel.broker-job-transport` | `1` | Async transport capability; workload/tenant/consumer | delivery transport only; authority: outbox/process/inbox truth; continuity: leases/checkpoints | unavailable → `queued_or_deferred`; saturated/throttled → `shed_or_reject` at admission; gap/identity conflict → `reconciliation_blocked` | workload/tenant/consumer and live-vs-maintenance capacity; resume after durable intent/checkpoint reconciliation | `FV-ASYNC-001`, `FV-OVER-003`; `RB-REL-009`, `RB-REL-013`; `OPEN-REL-009`, `OPEN-REL-012`, `OPEN-REL-025` |
| `rel.consumer-inbox-effect` | `1` | Consumer contract owner; tenant/source/contract | inbox content equivalence plus effect/result truth; hard: transaction/effect authority; continuity: lease and dedup horizon | duplicate → accepted dedup path; identity conflict/ambiguous → `reconciliation_blocked`; poison/permanent → `capability_unavailable` plus quarantine | tenant/source/contract and effect destination; resume after outcome/equivalence proof and current admission | `FV-ASYNC-002`, `FV-ASYNC-003`, `FV-ASYNC-004`; `RB-REL-010`, `RB-REL-011`; `OPEN-REL-012`, `OPEN-REL-025` |
| `rel.external-provider` | `1` | Owning application process plus provider adapter; tenant/integration/provider/destination | stable platform operation and authoritative provider inquiry/result; hard: local operation ledger; external: provider | unavailable/slow/throttled → `fail_fast` or bounded `queued_or_deferred`; ambiguous → `reconciliation_blocked`; compromised/permanent → `capability_unavailable` | tenant/integration/provider/destination concurrency and circuit; resume after provider/local outcome reconciliation and gradual probes | `FV-EXT-001`, `FV-EXT-002`; `RB-REL-007`, `RB-REL-008`; `OPEN-REL-005`, `OPEN-REL-006`, `OPEN-REL-007`, `OPEN-REL-008`, `OPEN-REL-011`, `OPEN-REL-014` |
| `rel.realtime-fanout` | `1` | Realtime delivery capability; connection/tenant/topic/cell | authoritative API/read truth plus current auth/placement and cursor; optional: fanout transport | unavailable/gap → `resync_required`; saturated → `shed_or_reject`; stale/policy denied → `fail_closed` | connection/tenant/topic/cell; resume after fresh auth/placement and authoritative resync | `FV-RT-001`, `FV-RT-002`; `RB-REL-014`; `OPEN-REL-017` |
| `rel.webhook-delivery` | `1` | Product-approved webhook contract owner; tenant/subscription/destination generation | immutable delivery obligation/attempt ledger and current destination generation; external: destination | unavailable/throttled → bounded `queued_or_deferred`; ambiguous → `reconciliation_blocked`; retired/policy denied → `capability_unavailable` or quarantine | tenant/subscription/destination generation; resume/redrive only under original Product-approved eligibility | `FV-WH-001`, `FV-WH-002`; `RB-REL-015`; `OPEN-REL-018` |
| `rel.telemetry-plane` | `1` | Optional telemetry capability with Security/Data policy; tenant/source/optional data class | accepted optional telemetry classification and source generation; async: ingestion; authority: business truth remains elsewhere | unavailable/saturated → `shed_or_reject`; gap → explicit `capability_unavailable` | telemetry isolated from transactional core and tenant/source cardinality; resume after loss/classification/dedup disposition | `FV-TEL-001`, `FV-EVID-001`; `RB-REL-017`, `RB-REL-022`; `OPEN-REL-020`, `OPEN-REL-026` |
| `rel.customer-telemetry-acceptance` | `1` | Customer-monitoring ingestion capability with Data authority; tenant/integration/source/generation/observation scope | canonical scoped observation identity plus durable acceptance record/journal; async: historical/current-state/signal projections; continuity: acceptance/projection watermarks and transition intent | unavailable → bounded `queued_or_deferred` without acknowledgement; saturated → `shed_or_reject` only before acceptance; duplicate → `fail_fast` dedup; identity conflict/gap/recovery blocked → `reconciliation_blocked` | acceptance and projection workloads isolated by tenant/source; resume after durable responsibility, monotonic projection and transition/checkpoint reconciliation | `FV-TEL-002`, `FV-EVID-001`; `RB-REL-026`, `RB-REL-022`; `OPEN-REL-009`, `OPEN-REL-020`, `OPEN-REL-025`, `OPEN-REL-026`, `OPEN-REL-030` |
| `rel.mandatory-audit-plane` | `1` | Owning protected-effect capability with Security/Data audit policy; tenant/subject/effect/source | durable mandatory audit responsibility joined to the protected effect; hard: audit durability/authority; continuity: audit identity and governance | unavailable/saturated/gap/governance blocked → `fail_closed` for the affected protected effect | audit path isolated from optional telemetry and scoped by tenant/subject/effect/source; resume after durable responsibility and continuity proof | `FV-AUDIT-001`, `FV-EVID-001`; `RB-REL-017`, `RB-REL-022`; `OPEN-REL-020`, `OPEN-REL-026` |
| `rel.artifact-storage` | `1` | Artifact/governance owner; tenant/artifact/generation | transactional metadata/releasability plus verified object hash/length; external: object data plane; continuity: erasure/hold/revocation | unavailable/mismatch → `capability_unavailable`; stale/governance blocked → `fail_closed`; ambiguous lifecycle → `reconciliation_blocked` | tenant/artifact/generation and stream/lease; resume after integrity and governance-fence reconciliation | `FV-ART-001`, `FV-ART-002`; `RB-REL-016`; `OPEN-REL-019`, `OPEN-REL-025` |
| `rel.reporting-derived` | `1` | Reporting/derived capability; tenant/report/workload | authoritative source data; optional: projection/report stores and queues | unavailable/slow → `queued_or_deferred`; saturated → `shed_or_reject`; stale → explicit `stale_tolerant` only if Product permits | separate tenant/workload queue/pool and rebuild generation; resume after bounded backlog/dependency health | `FV-OVER-002`, `FV-OVER-003`; `RB-REL-013`; `OPEN-REL-008`, `OPEN-REL-009`, `OPEN-REL-010`, `OPEN-REL-022` |
| `rel.privileged-operations` | `1` | Owning admin/migration/recovery process with Security authority; explicit target scope | current scoped authorization, target truth, audit and stable operation identity; hard: security and transactional authority | unavailable/policy denied → `fail_closed`; timeout/ambiguous → `reconciliation_blocked`; saturated → `shed_or_reject` outside reserved recovery policy | dedicated trust/runtime/egress/resource envelope; resume after current authority, target state, audit and outcome proof | `FV-PRIV-001`, `FV-REC-003`; `RB-REL-020`; `OPEN-REL-014`, `OPEN-REL-021`, `OPEN-REL-024`, `OPEN-REL-027` |

### Canonical failure-to-mode bindings

The summary column above is explanatory. The following bindings are the machine-oriented values and use only the enums in `08-reliability-semantic-manifest.md`. A failure class not listed for a profile is unsupported and SHALL fail closed until a reviewed profile version classifies it.

| `reliability_profile_id` | `profile_version` | Canonical `failure_class:degradation_mode` bindings |
|---|---|---|
| `rel.control-plane-placement` | `1` | `unavailable:stale_tolerant`; `partitioned:stale_tolerant`; `stale:fail_closed`; `identity_conflict:fail_closed`; `recovery_continuity_blocked:reconciliation_blocked` |
| `rel.cell-transactional-store` | `1` | `unavailable:fail_closed`; `partitioned:fail_closed`; `slow_or_timed_out:fail_fast`; `recovery_continuity_blocked:reconciliation_blocked` |
| `rel.security-session-authority` | `1` | `unavailable:fail_closed`; `stale:fail_closed`; `compromised_or_untrusted:fail_closed`; `policy_denied:capability_unavailable` |
| `rel.placement-reference-cache` | `1` | `unavailable:fail_fast`; `stale:fail_closed`; `identity_conflict:fail_closed`; bounded current evidence uses `stale_tolerant` only under the profile lease |
| `rel.performance-cache` | `1` | `unavailable:fail_fast`; `stale:stale_tolerant` only under accepted Product semantics; `saturated:shed_or_reject` |
| `rel.replay-consume-state` | `1` | `unavailable:fail_closed`; `stale:fail_closed`; `out_of_order_or_gap:fail_closed`; `identity_conflict:reconciliation_blocked`; `contract_permanent:capability_unavailable`; `poison_or_unknown:capability_unavailable` |
| `rel.secret-key-authority` | `1` | `unavailable:capability_unavailable`; `stale:fail_closed`; `compromised_or_untrusted:fail_closed`; `governance_blocked:fail_closed` |
| `rel.configuration-authority` | `1` | `unavailable:stale_tolerant` only for verified permitted last-known-good; `contract_permanent:fail_closed`; `identity_conflict:fail_closed`; `out_of_order_or_gap:fail_closed`; `stale:fail_closed`; `compromised_or_untrusted:fail_closed`; `recovery_continuity_blocked:reconciliation_blocked` |
| `rel.outbox-publication` | `1` | `unavailable:queued_or_deferred`; `throttled:queued_or_deferred`; `identity_conflict:reconciliation_blocked`; `saturated:shed_or_reject` before acceptance |
| `rel.broker-job-transport` | `1` | `unavailable:queued_or_deferred`; `saturated:shed_or_reject`; `throttled:shed_or_reject`; `out_of_order_or_gap:reconciliation_blocked`; `identity_conflict:reconciliation_blocked` |
| `rel.consumer-inbox-effect` | `1` | `duplicate:fail_fast` through the accepted dedup/result-return path without effect re-execution; `identity_conflict:reconciliation_blocked`; `external_outcome_ambiguous:reconciliation_blocked`; `poison_or_unknown:capability_unavailable`; `contract_permanent:capability_unavailable` |
| `rel.external-provider` | `1` | `unavailable:fail_fast`; `slow_or_timed_out:fail_fast`; `throttled:queued_or_deferred`; `external_outcome_ambiguous:reconciliation_blocked`; `compromised_or_untrusted:capability_unavailable`; `contract_permanent:capability_unavailable` |
| `rel.realtime-fanout` | `1` | `unavailable:resync_required`; `out_of_order_or_gap:resync_required`; `saturated:shed_or_reject`; `stale:fail_closed`; `policy_denied:fail_closed` |
| `rel.webhook-delivery` | `1` | `unavailable:queued_or_deferred`; `throttled:queued_or_deferred`; `external_outcome_ambiguous:reconciliation_blocked`; `policy_denied:capability_unavailable` |
| `rel.telemetry-plane` | `1` | `unavailable:shed_or_reject`; `saturated:shed_or_reject`; `out_of_order_or_gap:capability_unavailable` |
| `rel.customer-telemetry-acceptance` | `1` | `unavailable:queued_or_deferred`; `saturated:shed_or_reject` only before durable acceptance while accepted observations remain queued; `duplicate:fail_fast` through canonical scoped dedup; `identity_conflict:reconciliation_blocked`; `out_of_order_or_gap:reconciliation_blocked` for affected current-state/signal projection while historical acceptance remains durable; `recovery_continuity_blocked:reconciliation_blocked` |
| `rel.mandatory-audit-plane` | `1` | `unavailable:fail_closed`; `saturated:fail_closed`; `out_of_order_or_gap:fail_closed`; `governance_blocked:fail_closed` |
| `rel.artifact-storage` | `1` | `unavailable:capability_unavailable`; `identity_conflict:capability_unavailable`; `stale:fail_closed`; `governance_blocked:fail_closed`; `external_outcome_ambiguous:reconciliation_blocked` |
| `rel.reporting-derived` | `1` | `unavailable:queued_or_deferred`; `slow_or_timed_out:queued_or_deferred`; `saturated:shed_or_reject`; `stale:stale_tolerant` only if Product permits |
| `rel.privileged-operations` | `1` | `unavailable:fail_closed`; `policy_denied:fail_closed`; `slow_or_timed_out:reconciliation_blocked`; `external_outcome_ambiguous:reconciliation_blocked`; `saturated:shed_or_reject` outside accepted recovery reservation |

### Canonical failure-to-vector bindings

This table materializes the required vector for every failure class accepted by each profile. It is part of the joined `fault_vectors` field; a listed vector cannot be removed by the profile-specific component or cross-profile selector.

| Profile key | Canonical `failure_class -> fault_vector` bindings |
|---|---|
| `rel.control-plane-placement@1` | `unavailable→FV-CP-001`; `partitioned→FV-CP-001`; `stale→FV-CP-002`; `identity_conflict→FV-CP-002`; `recovery_continuity_blocked→FV-REC-002` |
| `rel.cell-transactional-store@1` | `unavailable→FV-CELL-001`; `partitioned→FV-CELL-002`; `slow_or_timed_out→FV-RETRY-003`; `recovery_continuity_blocked→FV-REC-001,FV-REC-002` |
| `rel.security-session-authority@1` | `unavailable→FV-SEC-001`; `stale→FV-SEC-001`; `compromised_or_untrusted→FV-SEC-001`; `policy_denied→FV-SEC-001` |
| `rel.placement-reference-cache@1` | `unavailable→FV-CACHE-001`; `stale→FV-CP-002`; `identity_conflict→FV-CP-002` |
| `rel.performance-cache@1` | `unavailable→FV-CACHE-001`; `stale→FV-CACHE-001`; `saturated→FV-OVER-001,FV-OVER-002` |
| `rel.replay-consume-state@1` | `unavailable→FV-REC-003`; `stale→FV-REC-003`; `out_of_order_or_gap→FV-REC-003`; `identity_conflict→FV-ASYNC-003`; `contract_permanent→FV-ASYNC-004`; `poison_or_unknown→FV-ASYNC-004` |
| `rel.secret-key-authority@1` | `unavailable→FV-SECRET-001`; `stale→FV-SECRET-001`; `compromised_or_untrusted→FV-SECRET-001`; `governance_blocked→FV-SECRET-001` |
| `rel.configuration-authority@1` | `unavailable→FV-CONFIG-002`; `contract_permanent→FV-CONFIG-001`; `identity_conflict→FV-CONFIG-001`; `out_of_order_or_gap→FV-CONFIG-001`; `stale→FV-CONFIG-002`; `compromised_or_untrusted→FV-CONFIG-001`; `recovery_continuity_blocked→FV-CONFIG-002` |
| `rel.outbox-publication@1` | `unavailable→FV-ASYNC-001`; `throttled→FV-ASYNC-001`; `identity_conflict→FV-ASYNC-003`; `saturated→FV-ASYNC-001,FV-OVER-002` |
| `rel.broker-job-transport@1` | `unavailable→FV-ASYNC-001`; `saturated→FV-OVER-002,FV-OVER-003`; `throttled→FV-ASYNC-001`; `out_of_order_or_gap→FV-ASYNC-003`; `identity_conflict→FV-ASYNC-003` |
| `rel.consumer-inbox-effect@1` | `duplicate→FV-ASYNC-002`; `identity_conflict→FV-ASYNC-003`; `external_outcome_ambiguous→FV-ASYNC-002,FV-RETRY-003`; `poison_or_unknown→FV-ASYNC-004`; `contract_permanent→FV-ASYNC-004` |
| `rel.external-provider@1` | `unavailable→FV-EXT-001`; `slow_or_timed_out→FV-EXT-001`; `throttled→FV-EXT-001,FV-CIRCUIT-001`; `external_outcome_ambiguous→FV-EXT-002`; `compromised_or_untrusted→FV-EXT-003`; `contract_permanent→FV-EXT-003` |
| `rel.realtime-fanout@1` | `unavailable→FV-RT-001`; `out_of_order_or_gap→FV-RT-001`; `saturated→FV-RT-001`; `stale→FV-RT-002`; `policy_denied→FV-RT-002` |
| `rel.webhook-delivery@1` | `unavailable→FV-WH-001`; `throttled→FV-WH-001`; `external_outcome_ambiguous→FV-WH-002`; `policy_denied→FV-WH-002` |
| `rel.telemetry-plane@1` | `unavailable→FV-TEL-001`; `saturated→FV-TEL-001`; `out_of_order_or_gap→FV-TEL-001` |
| `rel.customer-telemetry-acceptance@1` | `unavailable→FV-TEL-002`; `saturated→FV-TEL-002`; `duplicate→FV-TEL-002`; `identity_conflict→FV-TEL-002`; `out_of_order_or_gap→FV-TEL-002`; `recovery_continuity_blocked→FV-TEL-002` |
| `rel.mandatory-audit-plane@1` | `unavailable→FV-AUDIT-001`; `saturated→FV-AUDIT-001`; `out_of_order_or_gap→FV-AUDIT-001`; `governance_blocked→FV-AUDIT-001` |
| `rel.artifact-storage@1` | `unavailable→FV-ART-001`; `identity_conflict→FV-ART-001`; `stale→FV-ART-002`; `governance_blocked→FV-ART-002`; `external_outcome_ambiguous→FV-ART-001,FV-ART-002` |
| `rel.reporting-derived@1` | `unavailable→FV-OVER-002`; `slow_or_timed_out→FV-OVER-002`; `saturated→FV-OVER-002,FV-OVER-003`; `stale→FV-OVER-002` |
| `rel.privileged-operations@1` | `unavailable→FV-PRIV-001`; `policy_denied→FV-PRIV-001`; `slow_or_timed_out→FV-RETRY-003,FV-PRIV-001`; `external_outcome_ambiguous→FV-RETRY-003,FV-PRIV-001`; `saturated→FV-PRIV-001` |

### Cross-profile bindings

| Profile selector | Mandatory evidence/blocker/OPEN bindings |
|---|---|
| every `rel.*` profile and every version | `FV-RETRY-001`, `FV-RETRY-002`, `FV-RETRY-003`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001`; `RB-REL-021`, `RB-REL-022`, `RB-REL-024`, `RB-REL-025`; `OPEN-REL-006`, `OPEN-REL-007`, `OPEN-REL-021`, `OPEN-REL-022`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |

The selector is normative and mechanically expands to every catalog key; it is not an optional inheritance rule. A profile version cannot opt out of compatibility or evidence-integrity coverage.

## Complete normalized manifest materialization

The catalog table materializes `owning_capability`, `scope`, `truth_authority` and `dependency_set`; the canonical binding tables materialize `failure_classes`, one `degradation_mode` and at least one `fault_vector` for every listed class. The following tables materialize every remaining required field. Their exact key is the same pair `reliability_profile_id` plus `profile_version`; joining the catalog, bindings and completion rows yields one complete record per key. A missing row, duplicate key, empty field or unresolved identifier is a Phase 11 conformance blocker.

### Status and applicability fields

Applicability is a canonical set, not an example or runtime inventory. A runtime operation, contract or role outside the selected set is unsupported by that profile version and SHALL fail closed until a reviewed profile version classifies it.

| Profile key | `status` | Applicable operation/contract/runtime-role classes |
|---|---|---|
| `rel.control-plane-placement@1` | `proposed` | tenant placement lookup; cell admission/lifecycle; relocation/failover coordination; Platform Management role |
| `rel.cell-transactional-store@1` | `proposed` | authoritative tenant mutation/read transaction; idempotency/inbox/outbox/effect-ledger transaction; cell API/worker role |
| `rel.security-session-authority@1` | `proposed` | authentication verification; authorization decision; session/revocation/deny check; Security authority role |
| `rel.placement-reference-cache@1` | `proposed` | placement/reference lookup and refill; destination admission support; cell/API routing role |
| `rel.performance-cache@1` | `proposed` | Product-authorized derived read cache lookup/refill; application API/worker role |
| `rel.replay-consume-state@1` | `proposed` | replay admission; consume/dedup/equivalence lookup; API/event consumer authority role |
| `rel.secret-key-authority@1` | `proposed` | secret/key bootstrap, lease, renewal, rotation, revocation and crypto-erasure check; cryptographic authority/runtime role |
| `rel.configuration-authority@1` | `proposed` | configuration validate/publish/distribute/apply/restore; configuration owner and Platform Management distribution role |
| `rel.outbox-publication@1` | `proposed` | atomic outbox creation and durable publication dispatch; transactional producer/dispatcher role |
| `rel.broker-job-transport@1` | `proposed` | event/job enqueue, delivery, lease, checkpoint and transport redrive; broker adapter/worker role |
| `rel.consumer-inbox-effect@1` | `proposed` | event/job consume, inbox/effect commit, dedup, quarantine and governed redrive; consumer role |
| `rel.external-provider@1` | `proposed` | provider inquiry and Product-authorized external effect; provider-adapter/application role |
| `rel.realtime-fanout@1` | `proposed` | realtime connect, subscribe, fanout, cursor resume and authoritative resync; realtime gateway/fanout role |
| `rel.webhook-delivery@1` | `proposed` | Product-approved webhook obligation, attempt, inquiry, quarantine and redrive; webhook delivery role |
| `rel.telemetry-plane@1` | `proposed` | optional telemetry accept, buffer, transport, shed and gap disposition; telemetry producer/ingestion role |
| `rel.customer-telemetry-acceptance@1` | `proposed` | customer monitoring observation validation, durable acceptance, historical/current-state projection, checkpoint/replay/reconciliation and transition-signal obligation; monitoring adapter/ingestion/projector role |
| `rel.mandatory-audit-plane@1` | `proposed` | protected-effect audit admission, durable responsibility, ordering and recovery; audit authority/writer role |
| `rel.artifact-storage@1` | `proposed` | artifact upload/finalize/read/stream, integrity verification and lifecycle governance; artifact service/worker role |
| `rel.reporting-derived@1` | `proposed` | report/projection/rebuild/backfill and other Product-authorized derived work; reporting/derived worker role |
| `rel.privileged-operations@1` | `proposed` | admin, migration, recovery, parser, automation and other explicitly privileged target-scoped operation; specialized privileged role |

The following derived fields are normative, deterministic joins rather than defaults:

```text
ALL-FAULT-VECTORS(profile_key) = distinct(
  failure_to_vector_bindings[profile_key].fault_vectors
  union profile_fault_fields[profile_key].profile_specific_fault_vectors
  union circuit_policy_registry[selected_circuit_policy].evidence_vectors
  union cross_profile_selector.fault_vectors
)

ALL-RELEASE-BLOCKERS(profile_key) = distinct(
  profile_fault_fields[profile_key].profile_specific_release_blockers
  union cross_profile_selector.release_blockers
  union validation_matrix[ALL-FAULT-VECTORS(profile_key)].release_blocker
)
```

Every referenced vector and blocker SHALL exist, and each vector SHALL resolve to exactly one blocker row in `09-reliability-validation-and-fault-matrix.md`. Static conformance SHALL reject any profile for which an element of `ALL-FAULT-VECTORS` is absent from evidence or its vector-derived blocker is absent from `ALL-RELEASE-BLOCKERS`.

`E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` is a fully defined evidence value, not an inherited default: `design_acceptance` requires the reviewed manifest/vector/blocker/authority trace; `implementation_conformance` requires deterministic tests for the complete final vector set against the exact artifact, configuration and profile version; `release_evidence` requires admitted mixed-version combinations plus security, capacity and recovery dispositions; `runtime_evidence` requires isolated reproducible fault/recovery rehearsal at representative scale. Every row below selects this exact final set, including binding-derived and circuit-policy vectors.

`CAPACITY-NUMERICS` is a fully resolved `capacity_cost` subpolicy: every numeric capacity envelope and rearchitecture trigger remains owned by `OPEN-REL-022`, with Product/business plus Capacity-overlay authority, representative benchmark/cost evidence and production-eligibility closure. Each profile selects it explicitly below; profile-specific capacity OPENs remain additional constraints.

### Authority, criticality and prohibited fallback fields

| Profile key | `authority_refs` | `criticality` | `prohibited_fallbacks` |
|---|---|---|---|
| `rel.control-plane-placement@1` | `ADR-002`, `ADR-004`, `ADR-017`, `ADR-018`, `ADR-019`, `TM-REL-001`, `TM-REL-006` | authority/correctness/recovery critical; confidential tenant placement; fleet control blast with cell containment; durable generations | new placement or lifecycle grant from stale/missing evidence; unbounded local autonomy; retired generation admission |
| `rel.cell-transactional-store@1` | `ADR-002`, `ADR-004`, `ADR-006`, `ADR-017`, `ADR-018`, `ADR-019`, `TM-REL-006` | transactional-truth/durability/recovery critical; governed tenant data; cell blast radius | cache/replica reachability as write authority; queued truth-dependent mutation; dual writer; restore as authority |
| `rel.security-session-authority@1` | accepted Security requirements, `ADR-005`, `ADR-017`, `ADR-018`, `TM-REL-003` | authority/confidentiality/correctness critical; tenant/principal blast; revocation continuity | missing/stale positive evidence as permission; generic identity; deny/revocation regression |
| `rel.placement-reference-cache@1` | `ADR-002`, `ADR-004`, `ADR-012`, `ADR-017`, `ADR-019`, `TM-REL-001` | authority-sensitive derived copy; confidential placement; tenant/cell blast; generation continuity | cache presence as truth; stale allow over current deny; fallback without destination admission |
| `rel.performance-cache@1` | `ADR-012`, `ADR-017`, `TM-REL-007` | derived/reconstructable; correctness guarded by origin; tenant/workload blast; amplification-sensitive | stale data without Product authority; cache as mutation truth; unbounded origin refill |
| `rel.replay-consume-state@1` | accepted Data Architecture, Phase 09/10, `ADR-009`, `ADR-010`, `ADR-017`, `ADR-018`, `TM-REL-005`, `TM-REL-006` | authority/correctness/continuity critical; tenant/source blast; durable equivalence horizon | loss as unused capability; identity conflict overwrite; guessed replay eligibility |
| `rel.secret-key-authority@1` | accepted Security requirements, `ADR-015`, `ADR-017`, `ADR-018`, `TM-REL-003` | authority/confidentiality/recovery critical; namespace blast; rotation/erasure continuity | plaintext/default secret; stale lease beyond policy; namespace widening; erasure regression |
| `rel.configuration-authority@1` | accepted Security/System Design, `ADR-016`, `ADR-017`, `ADR-018`, `TM-REL-002` | authority/correctness/recovery critical; tenant/cell/role or fleet blast by scope; durable generation | permissive default; transport success as authority; partial rollout as complete; older generation silently winning |
| `rel.outbox-publication@1` | accepted Data Architecture and Phase 10, `ADR-009`, `ADR-017`, `TM-REL-005` | durable-progress/correctness critical; cell/producer blast; message continuity | publish without committed intent; rewrite identity during drain; unbounded accepted backlog |
| `rel.broker-job-transport@1` | Phase 10, `ADR-009`, `ADR-017`, `TM-REL-005`, `TM-REL-007` | durable-progress transport; tenant/workload blast; amplification and checkpoint continuity | broker delivery as business truth; unbounded queue; lease expiry as effect absence; identity rewrite |
| `rel.consumer-inbox-effect@1` | accepted Data Architecture and Phase 10, `ADR-009`, `ADR-017`, `TM-REL-004`, `TM-REL-005` | correctness/continuity/durability critical; tenant/source/effect blast | acknowledgement before durability; blind duplicate execution; conflict overwrite; poison infinite retry |
| `rel.external-provider@1` | `ADR-008`, `ADR-013`, `ADR-017`, `TM-REL-004`, `TM-REL-008` | correctness/continuity critical for effectful calls; tenant/provider blast; egress/confidentiality sensitive | timeout as absence; provider identity as domain authority; blind retry; shared global circuit/pool |
| `rel.realtime-fanout@1` | Phase 09/10, `ADR-011`, `ADR-017`, `TM-REL-007` | derived/advisory; authority-sensitive session; tenant/topic/cell blast; resync continuity | notification as truth; stale resume token as authority; unbounded replay; cross-tenant topic |
| `rel.webhook-delivery@1` | Product gate and Phase 10, `ADR-013`, `ADR-017`, `TM-REL-008` | product-gated continuity/confidentiality; tenant/destination blast; immutable delivery obligation | feature before Product gate; retarget old obligation; ambiguity erase; cross-destination queue/pool |
| `rel.telemetry-plane@1` | accepted Security/Data policy, `ADR-014`, `ADR-017`, `TM-REL-007`, `TM-REL-010` | optional/derived; confidentiality governed; tenant/source blast; cardinality/cost amplification | telemetry as business authority; fabricated completeness; unbounded buffer/cardinality; payload/secret fallback |
| `rel.customer-telemetry-acceptance@1` | accepted Data Architecture telemetry plane, `ADR-006`, `ADR-008`, `ADR-009`, `ADR-017`, `ADR-018`, `ADR-019`, `TM-REL-005`, `TM-REL-007` | correctness/durability/continuity critical after acceptance; governed customer data; tenant/source/generation blast; projection and relocation continuity | optional-loss policy after durable acceptance; acknowledgement before durable responsibility; provider-local identity as global scope; stale projection regression; memory-only transition intent |
| `rel.mandatory-audit-plane@1` | accepted Security/Data audit policy, `ADR-014`, `ADR-017`, `ADR-018`, `TM-REL-010` | authority/accountability/durability/confidentiality critical; tenant/subject/effect blast; audit continuity | protected effect without durable audit responsibility; downgrade to optional telemetry; reconstructed success |
| `rel.artifact-storage@1` | accepted Data/Security authority, `ADR-017`, `ADR-018`, `TM-REL-009` | integrity/confidentiality/governance/recovery critical; tenant/artifact blast; lifecycle continuity | object presence as releasability; stale capability; metadata/content mismatch; erasure/revocation resurrection |
| `rel.reporting-derived@1` | accepted Product/Quality authority, `ADR-017`, `TM-REL-007` | optional/derived unless Product reclassifies; tenant/workload blast; capacity/cost sensitive | derived data as authority; live-pool starvation; unbounded backlog; stale output without disclosure |
| `rel.privileged-operations@1` | accepted Security/System Design, `ADR-015`, `ADR-017`, `ADR-018`, `TM-REL-004`, `TM-REL-006`, `TM-REL-008` | authority/correctness/confidentiality/recovery critical; explicit target blast; privileged effect continuity | ordinary worker privilege; timeout as absence; unscoped target/egress; unaudited or blind recovery action |

### Identity, deadline, retry and circuit fields

Each `retry_policy` and `circuit_policy` value below is an explicit reference to a complete record in the registries that follow. The reference is part of the joined profile record; no prose or implementation default supplies omitted subfields.

| Profile key | `identity_policy` | `deadline_timeout_policy` | `retry_policy` | `circuit_policy` |
|---|---|---|---|---|
| `rel.control-plane-placement@1` | preserve tenant, placement, cell and authority generation | caller/end-to-end bound; lease expiry removes eligibility, never proves state absence | `RP-INQUIRY` | `CP-AUTHORITY` |
| `rel.cell-transactional-store@1` | preserve transaction, tenant, cell and writer generation | transaction deadline bounds waiting; cancellation/timeout never proves commit absence | `RP-RECONCILED-EFFECT` | `CP-AUTHORITY` |
| `rel.security-session-authority@1` | preserve principal, tenant, scope, credential and deny/revocation generation | protected decision ends when current verification cannot complete in caller budget | `RP-INQUIRY` | `CP-AUTHORITY` |
| `rel.placement-reference-cache@1` | key by tenant, cell and placement generation | freshness lease and caller budget both bind; expiry fails closed | `RP-REFILL` | `CP-CACHE` |
| `rel.performance-cache@1` | key by tenant, operation and source version | cache lookup cannot extend caller deadline; origin fallback inherits remaining budget | `RP-REFILL` | `CP-CACHE` |
| `rel.replay-consume-state@1` | preserve capability, tenant, source, epoch and consumption identity | lookup timeout/absence is uncertainty and fails protected admission | `RP-RECONCILED-EFFECT` | `CP-AUTHORITY` |
| `rel.secret-key-authority@1` | bind lease to secret/key generation, namespace and runtime identity | bootstrap/renewal uses caller and lease bounds; expiry cannot be extended locally | `RP-INQUIRY` | `CP-AUTHORITY` |
| `rel.configuration-authority@1` | bind content hash, schema, scope, applicability and monotonic generation | fetch/apply uses rollout and caller bounds; timeout cannot mark rollout complete | `RP-INQUIRY` | `CP-AUTHORITY` |
| `rel.outbox-publication@1` | preserve transaction, producer/source generation and immutable message identity | publication deadline is separate from originating commit; timeout preserves pending intent | `RP-DURABLE-TRANSPORT` | `CP-ASYNC` |
| `rel.broker-job-transport@1` | preserve message/job, tenant, source, consumer, lease and checkpoint identity | delivery/lease deadlines do not prove effect absence | `RP-DURABLE-TRANSPORT` | `CP-ASYNC` |
| `rel.consumer-inbox-effect@1` | preserve message/content equivalence, operation/effect and lease generation | handler/lease timeout is ambiguous until inbox/effect truth is queried | `RP-DURABLE-EFFECT` | `CP-ASYNC` |
| `rel.external-provider@1` | preserve platform operation, tenant, provider and destination generation across attempts | stage and overall deadlines; lost response creates external ambiguity, not absence | `RP-DURABLE-EFFECT` | `CP-EXTERNAL` |
| `rel.realtime-fanout@1` | preserve session, subject, tenant, topic, cursor and placement/auth generations | connection/write deadlines bound delivery only; timeout never changes business truth | `RP-RESYNC` | `CP-DELIVERY` |
| `rel.webhook-delivery@1` | preserve immutable delivery, subscription, tenant and destination generation | per-attempt and aggregate delivery bounds; lost response remains ambiguous | `RP-DURABLE-EFFECT` | `CP-EXTERNAL` |
| `rel.telemetry-plane@1` | preserve telemetry record/source/tenant/classification identity when accepted | telemetry work cannot extend business deadline; late optional records follow declared loss policy | `RP-OPTIONAL-TRANSPORT` | `CP-DELIVERY` |
| `rel.customer-telemetry-acceptance@1` | preserve trusted observation identity scope, observation ID, tenant, integration/source generation, projection order token, transition identity and checkpoints | no acknowledgement before durable acceptance; downstream deadlines preserve accepted responsibility and monotonic projection uncertainty | `RP-DURABLE-OBSERVATION` | `CP-DURABLE-ACCEPTANCE` |
| `rel.mandatory-audit-plane@1` | preserve audit, subject, tenant, protected effect and source generation identity | protected-effect deadline includes durable audit responsibility boundary; timeout fails closed | `RP-DURABLE-EFFECT` | `CP-AUTHORITY` |
| `rel.artifact-storage@1` | preserve tenant, artifact, upload/stream lease, object hash and governance generation | transfer deadlines do not prove completion; streaming continuation rechecks accepted fences | `RP-DURABLE-TRANSFER` | `CP-DELIVERY` |
| `rel.reporting-derived@1` | preserve tenant, report/work item, source version and rebuild generation | derived work yields at deadline and preserves checkpoint; cannot extend live-work budget | `RP-CHECKPOINTED-WORK` | `CP-DELIVERY` |
| `rel.privileged-operations@1` | preserve principal, target tenant/cell/resource, operation/effect and authority generation | deadline/lease expiry never proves privileged effect absence | `RP-RECONCILED-EFFECT` | `CP-AUTHORITY` |

#### Complete retry-policy registry

| Policy | Eligibility and safety | Aggregate budget | Backoff | Jitter | Terminal behavior |
|---|---|---|---|---|---|
| `RP-INQUIRY` | same current read/inquiry identity; current authority/scope revalidated; never repeats the protected effect | attempts, elapsed time, concurrency, queued count, queued bytes and attributable cost use `OPEN-REL-006`; speculation=`no_applicable_case` because parallel inquiry is forbidden; redrive=`no_applicable_case`; restart cannot reset any consumed dimension | pressure-reducing delay inside deadline/lease; validated hints only; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/operation/dependency; distribution=`OPEN-REL-006`; synchronized fleet schedule forbidden | profile fail-closed/unavailable mode after exhaustion; no result is invented and no protected action is admitted |
| `RP-REFILL` | same tenant/key/source generation under single-flight and authoritative-origin safety | attempts, elapsed time, concurrency, queued refill count, queued bytes, origin bytes/load and attributable cost use `OPEN-REL-006`; speculation=`no_applicable_case` because single-flight forbids parallel refill; redrive=`no_applicable_case`; restart preserves every consumed dimension | pressure-reducing delay within caller deadline and freshness horizon; validated hints only; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/key/origin; distribution=`OPEN-REL-006`; synchronized refill forbidden | bypass only to authoritative origin when safe/bounded; otherwise exact profile failure mode, never stale-authority expansion |
| `RP-RECONCILED-EFFECT` | only durable evidence proves no commit/effect boundary was crossed or reconciliation explicitly authorizes a same-identity attempt | attempts, elapsed time, concurrency, queued count, bytes and attributable cost across caller/worker/adapter/recovery/redrive use `OPEN-REL-006`; speculation=`no_applicable_case` unless a later profile version proves semantic safety; restart/relocation preserves every consumed dimension | pressure-reducing delay bounded by deadline and reconciliation/retention horizon; validated hints only; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/operation/target generation; distribution=`OPEN-REL-006`; synchronized redrive forbidden | `reconciliation_blocked` or `fail_closed`; ambiguity is never converted to absence and new identity is forbidden |
| `RP-DURABLE-TRANSPORT` | same immutable message/job identity after durable responsibility; current source/tenant/consumer generation required | attempts, elapsed time/queue age, concurrency, queued count, queued bytes, transport bytes and attributable cost including redrive use `OPEN-REL-006`; speculation=`no_applicable_case`; restart preserves every consumed dimension | pressure-reducing delay inside retention/deadline; validated transport hints only; numeric curve/cap=`OPEN-REL-006`; no restart reset | decorrelated by tenant/source/consumer/partition-equivalent scope; distribution=`OPEN-REL-006` | durable pending state, explicit expiry or quarantine under accepted contract; no identity rewrite or lost accepted work |
| `RP-DURABLE-EFFECT` | same operation/delivery/effect identity; idempotency/dedup or authoritative reconciliation plus current destination/authority required | attempts, elapsed time, concurrency, queued count, queued bytes, request/response bytes and attributable cost across caller/worker/adapter/provider/redrive use `OPEN-REL-006`; speculation=every speculative attempt consumes the same budget and requires separate semantic authorization; restart preserves all dimensions | pressure-reducing delay inside deadline/retention/reconciliation horizon; validated hints only; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/provider/destination/effect; distribution=`OPEN-REL-006`; synchronized destination recovery forbidden | `reconciliation_blocked`, quarantine or declared permanent failure; blind retry/new identity prohibited |
| `RP-RESYNC` | reconnect only after current auth/placement and accepted cursor/resync eligibility | attempts, elapsed time, concurrency, queued reconnect count, cursor/replay bytes and attributable cost use `OPEN-REL-006`; speculation=`no_applicable_case`; redrive=`no_applicable_case`; restart preserves all consumed dimensions | pressure-reducing delay inside session policy; numeric curve/cap=`OPEN-REL-006`; reconnect storms forbidden | decorrelated by tenant/session/topic/cell; distribution=`OPEN-REL-006` | `resync_required` or transport rejection; realtime never becomes business truth |
| `RP-OPTIONAL-TRANSPORT` | optional same-record/source identity only while data-class policy and capacity admit | attempts, elapsed time, concurrency, buffered count, buffered bytes, cardinality and attributable cost use `OPEN-REL-006`; speculation=`no_applicable_case`; redrive=`no_applicable_case` unless a later accepted data-class profile authorizes it; restart preserves accepted-buffer budget | pressure-reducing delay before explicit shedding; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/source/data class; distribution=`OPEN-REL-006` | `shed_or_reject` with explicit loss; cannot block business truth or claim completeness |
| `RP-DURABLE-OBSERVATION` | same trusted scoped observation identity before acceptance; after durable acceptance, only the same observation/transition identities and monotonic projection contract may be replayed | attempts, elapsed time/queue age, concurrency, buffered/accepted/backlog count, buffered/accepted/projected bytes, storage/cardinality and attributable cost across intake/projection/replay use `OPEN-REL-006`; speculation=`no_applicable_case` because parallel acceptance is forbidden; redrive/replay consumes the same profile budget; restart/relocation preserves every dimension | pressure-reducing delay inside source, retention and checkpoint horizons; validated source hints only; numeric curve/cap=`OPEN-REL-006`; no restart reset | decorrelated by tenant/integration/source/generation/projection; distribution=`OPEN-REL-006`; synchronized projection replay forbidden | before acceptance, explicit defer/reject without acknowledgement; after acceptance, durable pending/reconciliation state until historical/current-state/signal obligations converge; accepted observation is never dropped or reclassified optional |
| `RP-DURABLE-TRANSFER` | same tenant/artifact/hash/lease and current governance generation; verified chunk equivalence | attempts, elapsed time, concurrency, queued transfer count, transferred/queued bytes, object calls and attributable cost use `OPEN-REL-006`; speculation=parallel chunks consume the same budget and require verified non-overlap; redrive=`no_applicable_case`; restart preserves all dimensions | pressure-reducing delay inside transfer lease and governance horizon; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/artifact/object-plane scope; distribution=`OPEN-REL-006` | explicit unavailable/reconciliation state; no false completion, integrity bypass or stale continuation |
| `RP-CHECKPOINTED-WORK` | same tenant/work item/source/rebuild generation and durable checkpoint | attempts, elapsed time, concurrency, queued count, queue/input/output bytes, compute and attributable cost including resumed/redriven work use `OPEN-REL-006`; speculation=`no_applicable_case`; restart preserves consumed work and checkpoint | pressure-reducing delay yielding to live/recovery-critical work; numeric curve/cap=`OPEN-REL-006` | decorrelated by tenant/workload/dependency; distribution=`OPEN-REL-006` | checkpointed defer, explicit shed/expiry or capability unavailable; no restart-from-zero amplification |

#### Complete circuit-policy registry

Every circuit record below materializes the protected scope, counted/excluded failures, open behavior, probe concurrency, retry/backlog interaction, state-loss behavior, fallback authority, evidence and numeric OPEN. The selecting profile's own `fault_vectors` field supplies dependency-specific evidence in addition to the listed common vectors.

| Policy | Protected scope | Counted and excluded failures | Open and probe behavior | Retry/backlog and state-loss behavior | Fallback authority | Evidence and numeric OPENs |
|---|---|---|---|---|---|---|
| `CP-AUTHORITY` | authority dependency by the exact tenant/scope/generation selector below | only canonical selector-listed classes count; every other canonical class and caller cancellation is excluded | selector-listed open mapping is exact; probes are bounded read-only current-authority checks and cannot authorize mutation/effect | open stops selector-listed protected admission and preserves durable pending/ambiguity state; restart/state loss starts conservative with no fresh retry budget | exact selector-listed authority only; circuit state is never authority | `FV-RETRY-002`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`; numeric thresholds=`OPEN-REL-007` |
| `CP-CACHE` | tenant/key/origin/source-generation scope from the exact selector below | only canonical selector-listed classes count; every other canonical class and caller cancellation is excluded | selector-listed open mapping is exact; bounded single-flight probes cannot admit stale authority | refill/backlog remains bounded/fair; retry budget survives restart; state loss starts cold/conservative | exact selector-listed origin/current authority only | `FV-CACHE-001`, `FV-RETRY-002`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`; numeric thresholds=`OPEN-REL-007` |
| `CP-ASYNC` | producer/transport/consumer scope from the exact tenant/contract/workload selector below | only canonical selector-listed classes count; every other canonical class and caller cancellation is excluded | selector-listed open mapping is exact; probes preserve immutable identity and cannot acknowledge work | durable backlog remains bounded/attributable; retry budget, age, leases and checkpoints survive restart/state loss | exact selector-listed outbox/process/inbox/effect authority only; transport/circuit presence is not business authority | `FV-ASYNC-001`, `FV-OVER-001`, `FV-RETRY-002`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`; numeric thresholds=`OPEN-REL-007` |
| `CP-EXTERNAL` | tenant/integration/provider/destination/operation scope from the exact selector below | only canonical selector-listed classes count; every other canonical class and caller cancellation is excluded | selector-listed open mapping is exact; bounded half-open probes never imply prior outcome absence | backlog and retries remain destination-isolated under one aggregate budget; restart/state loss preserves ambiguous attempts | exact selector-listed local ledger and authoritative inquiry only; provider identity/circuit state is not domain authority | `FV-EXT-001`, `FV-EXT-002`, `FV-RETRY-002`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`; numeric thresholds=`OPEN-REL-007` |
| `CP-DURABLE-ACCEPTANCE` | tenant/integration/source/generation/acceptance/projection scope from the exact selector below; no broker, outbox, journal, stream or store topology is selected | only canonical selector-listed classes count; every other canonical class and caller cancellation is excluded | selector-listed open mapping is exact; bounded probes may establish present durable-acceptance/projection health but cannot acknowledge an observation without durable responsibility or discard accepted work | unacknowledged intake and accepted projection backlog remain separately bounded/attributable; scoped identity, watermarks, transition intent and consumed retry budget survive restart, recovery and relocation | exact selector-listed durable acceptance authority, accepted observation identity, projection checkpoints and monotonic transition state only; physical mechanism presence is not authority | `FV-TEL-002`, `FV-RETRY-002`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`; mechanism=`OPEN-REL-030`; numeric thresholds=`OPEN-REL-007` |
| `CP-DELIVERY` | tenant/source/data-class/session/artifact/workload scope from the exact selector below | only canonical selector-listed classes count; every other canonical class and caller cancellation is excluded | selector-listed open mapping is exact; probes are bounded and cannot restore authority | backlog/reconnect/transfer/work retries remain bounded and preserve consumed budget/checkpoint across state loss | exact selector-listed truth authority and current governance/auth/source generation only | `FV-OVER-001`, `FV-RETRY-002`, `FV-CIRCUIT-001`, `FV-CIRCUIT-002`; numeric thresholds=`OPEN-REL-007` |

#### Exact circuit selectors by profile

This keyed table completes the selected circuit record. `counted_failure_classes`, `excluded_failure_classes`, `open_degradation_mapping` and `fallback_authority` are literal joined fields. A canonical failure not in `counted_failure_classes` is excluded from dependency-health counting; it still follows the profile failure-to-mode binding. No implementation may add a counted class or choose a different open mode by default.

| Profile key | Counted canonical failure classes | Exact open degradation mapping | Exact fallback authority |
|---|---|---|---|
| `rel.control-plane-placement@1` | `unavailable`, `partitioned`, `stale`, `identity_conflict` | `unavailable→stale_tolerant` and `partitioned→stale_tolerant` only under verified unexpired placement lease plus destination admission; otherwise `fail_closed`; `stale→fail_closed`; `identity_conflict→fail_closed` | current Control Plane generation or the same verified bounded lease; no lifecycle/placement mutation |
| `rel.cell-transactional-store@1` | `unavailable`, `slow_or_timed_out`, `partitioned` | `unavailable→fail_closed`; `slow_or_timed_out→fail_fast` while commit uncertainty remains durable; `partitioned→fail_closed` | current single-writer transactional authority only |
| `rel.security-session-authority@1` | `unavailable`, `stale`, `compromised_or_untrusted` | `unavailable→fail_closed`; `stale→fail_closed`; `compromised_or_untrusted→fail_closed` | current authentication/authorization/revocation/deny authority only |
| `rel.placement-reference-cache@1` | `unavailable`, `stale`, `identity_conflict` | `unavailable→fail_fast` to current authority within remaining budget; `stale→fail_closed`; `identity_conflict→fail_closed` | current placement authority plus destination admission only |
| `rel.performance-cache@1` | `unavailable`, `saturated`, `stale` | `unavailable→fail_fast` to bounded origin; `saturated→shed_or_reject`; `stale→stale_tolerant` only under accepted Product semantics, otherwise `fail_fast` | authoritative origin under remaining deadline/bulkhead only |
| `rel.replay-consume-state@1` | `unavailable`, `stale`, `out_of_order_or_gap` | `unavailable→fail_closed`; `stale→fail_closed`; `out_of_order_or_gap→fail_closed` | current consumption/equivalence/dedup authority only |
| `rel.secret-key-authority@1` | `unavailable`, `stale`, `compromised_or_untrusted` | `unavailable→capability_unavailable`; `stale→fail_closed`; `compromised_or_untrusted→fail_closed` | current secret/key generation and valid namespace-bound lease only |
| `rel.configuration-authority@1` | `unavailable`, `stale`, `out_of_order_or_gap`, `identity_conflict`, `compromised_or_untrusted` | `unavailable→stale_tolerant` only for verified permitted last-known-good, otherwise `fail_closed`; every other counted class→`fail_closed` | current accepted configuration generation or verified permitted last-known-good only |
| `rel.outbox-publication@1` | `unavailable`, `throttled`, `saturated` | `unavailable→queued_or_deferred`; `throttled→queued_or_deferred`; `saturated→shed_or_reject` before originating commit | committed immutable outbox intent only |
| `rel.broker-job-transport@1` | `unavailable`, `throttled`, `saturated` | `unavailable→queued_or_deferred`; `throttled→shed_or_reject`; `saturated→shed_or_reject` | durable intent/checkpoint plus inbox/process authority only |
| `rel.consumer-inbox-effect@1` | `no_applicable_case(condition=v1 has no dependency-health class eligible to open a circuit; authority=accepted Phase 10 consumer contract plus this profile's failure bindings; evidence=FV-CIRCUIT-002)` | circuit cannot open from duplicate, identity conflict, ambiguity, poison or permanent content; those classes retain their exact profile modes | inbox/effect/result truth only |
| `rel.external-provider@1` | `unavailable`, `slow_or_timed_out`, `throttled` | `unavailable→fail_fast`; `slow_or_timed_out→fail_fast`; `throttled→queued_or_deferred` only for an already Product-authorized durable path, otherwise `fail_fast` | local operation ledger plus authoritative provider inquiry under current destination generation |
| `rel.realtime-fanout@1` | `unavailable`, `out_of_order_or_gap`, `saturated` | `unavailable→resync_required`; `out_of_order_or_gap→resync_required`; `saturated→shed_or_reject` | authoritative API/read truth plus current auth/placement/cursor only |
| `rel.webhook-delivery@1` | `unavailable`, `throttled` | `unavailable→queued_or_deferred`; `throttled→queued_or_deferred`, both only inside original Product-approved bounds | immutable delivery ledger plus current original destination-generation eligibility |
| `rel.telemetry-plane@1` | `unavailable`, `saturated`, `out_of_order_or_gap` | `unavailable→shed_or_reject`; `saturated→shed_or_reject`; `out_of_order_or_gap→capability_unavailable` for affected telemetry continuity | accepted optional telemetry classification/source generation only; no business fallback |
| `rel.customer-telemetry-acceptance@1` | `unavailable`, `saturated` | `unavailable→queued_or_deferred` within a bounded unacknowledged intake path or the durable accepted-observation backlog; `saturated→shed_or_reject` only before durable acceptance while every already-accepted observation remains durable and pending | canonical durable acceptance record/journal, accepted scoped identity, projection checkpoints and current monotonic transition intent only |
| `rel.mandatory-audit-plane@1` | `unavailable`, `saturated`, `out_of_order_or_gap`, `governance_blocked` | `unavailable→fail_closed`; `saturated→fail_closed`; `out_of_order_or_gap→fail_closed`; `governance_blocked→fail_closed` for the affected protected effect | durable mandatory-audit responsibility plus current audit governance only |
| `rel.artifact-storage@1` | `unavailable`, `identity_conflict`, `stale`, `governance_blocked` | `unavailable→capability_unavailable`; `identity_conflict→capability_unavailable`; `stale→fail_closed`; `governance_blocked→fail_closed` | transactional artifact metadata/releasability plus verified object integrity and current governance generation |
| `rel.reporting-derived@1` | `unavailable`, `slow_or_timed_out`, `saturated` | `unavailable→queued_or_deferred`; `slow_or_timed_out→queued_or_deferred`; `saturated→shed_or_reject` | authoritative source plus current rebuild/work generation only |
| `rel.privileged-operations@1` | `unavailable`, `slow_or_timed_out`, `saturated` | `unavailable→fail_closed`; `slow_or_timed_out→reconciliation_blocked`; `saturated→shed_or_reject` outside accepted reserved recovery capacity | current scoped authorization, target truth, audit and stable operation identity only |

For `rel.external-provider@1`, both `compromised_or_untrusted` and `contract_permanent` are deliberately excluded from circuit-health counting and ordinary half-open recovery. They retain their canonical `capability_unavailable` binding and `FV-EXT-003` evidence. A compromised trust disposition can be cleared only by independently accountable Security/integration authority from accepted evidence; circuit state, successful probe, elapsed time or provider response cannot re-enable it. A permanent contract result terminates the stable operation's ordinary retry/probe path; any later distinct operation requires its own accepted Product/contract cause and identity.

### Bulkhead, backpressure, ambiguity and recovery fields

| Profile key | `bulkhead_policy` | `backpressure_policy` | `ambiguity_policy` | `recovery_policy` |
|---|---|---|---|---|
| `rel.control-plane-placement@1` | separate Control Plane management from cells; tenant/lifecycle scope and recovery work isolated | stop topology/authority expansion; bound cached-lease users and reconciliation intake; deny on overflow | contradictory/missing generations remain explicit; Platform Management owns resolution; no mutation retry | recover non-authoritative; reconcile placement/deny/generations through `(R,F]`; destination admission plus current generation gates resume |
| `rel.cell-transactional-store@1` | cell is primary fault domain; tenant transactions and recovery workload bounded | reject new truth-dependent mutations when unavailable; bound reads/recovery; never queue mutation responsibility | timeout/failover commit uncertainty remains in transaction/idempotency ledger; owning use case reconciles | restored/failover candidate is non-authoritative; single writer fence and complete ledgers/`(R,F]` gate resume |
| `rel.security-session-authority@1` | principal/tenant/scope and authority dependency isolated from optional work | reject protected decisions when proof unavailable; bounded verification demand; no permissive overflow | uncertain auth/revocation is denial, not guessed state; Security authority owns current disposition | restore/failover cannot regress deny/revocation; current generation and audit continuity gate resume |
| `rel.placement-reference-cache@1` | tenant/generation keys and refill concurrency isolated by authority source | bound single-flight refill; expire/reject when lease/current admission is not provable | conflicting cache/source generations remain explicit and fail closed; authority source owns disposition | invalidate/rebuild as derived copy; current source and destination admission required before use |
| `rel.performance-cache@1` | tenant/operation/origin refill pools isolated | bound single-flight, queue and origin concurrency; shed/reject on overflow | stale/missing cache is not business ambiguity; authoritative origin decides or capability degrades | discard/rebuild under origin version and stampede control; no recovery authority |
| `rel.replay-consume-state@1` | tenant/source/capability epoch isolated | reject protected admission on missing continuity; bound rebuild/inquiry; no guessed overflow | missing/conflicting equivalence or consumption remains durable uncertainty owned by capability authority | restored state non-authoritative until epoch, dedup horizon and `(R,F]` continuity reconcile |
| `rel.secret-key-authority@1` | namespace/runtime/cell/tenant secret paths isolated | reject bootstrap/renewal when authority unavailable; bound fetch/rotation; no fallback buffer of plaintext | generation/lease contradiction fails closed and remains owned by cryptographic authority | reconcile rotation, revocation and crypto-erasure through recovery interval; current lease/authority gates resume |
| `rel.configuration-authority@1` | tenant/cell/role/config scope and rollout generation isolated | stop incompatible target admission; bound distribution/convergence; overflow cannot apply partial content | mixed/contradictory generations remain explicit; configuration owner establishes one accepted disposition | restore non-authoritative for config use until schema, target coverage and later governance reconcile through `(R,F]` |
| `rel.outbox-publication@1` | cell/producer/contract backlog and dispatcher isolated | accept only within bounded durable outbox capacity; reject before originating commit when full; fair live/recovery drain | publisher uncertainty preserves pending immutable intent; owning transactional capability reconciles | restore/replay same message/source generations; `(R,F]` outbox and acknowledgement continuity before drain |
| `rel.broker-job-transport@1` | workload/tenant/consumer plus live/maintenance/recovery pools isolated | bounded age/bytes/count admission, explicit overflow, fair checkpointed drain | transport uncertainty never decides business effect; inbox/process authority owns outcome | restore checkpoints/leases non-authoritatively; reconcile durable intent and consumer state before progress |
| `rel.consumer-inbox-effect@1` | tenant/source/contract/effect destination and poison quarantine isolated | bound concurrency/retry/quarantine; stop one item without partition/global starvation | durable inbox/effect ambiguity with owner/evidence; retry blocked until same-identity safety proven | restore inbox/effect/dedup/lease facts through `(R,F]`; current admission and outcome proof gate resume |
| `rel.external-provider@1` | tenant/integration/provider/destination/operation-class pools and circuits isolated | bound concurrency, attempts, queue age/bytes and recovery probes; explicit reject/defer by accepted contract | durable local ambiguous state; owning adapter/use case performs inquiry/reconciliation; no blind retry | reconcile local/provider outcomes and destination generation; gradual probe admission after evidence |
| `rel.realtime-fanout@1` | connection/tenant/topic/cell pools isolated from authoritative API and other tenants | bound connection buffers/cursors/fanout; shed transport and require resync on overflow | gaps/disconnects are delivery uncertainty only; authoritative read/resync owns convergence | no recovered fanout authority; revalidate auth/placement and resync from authoritative state |
| `rel.webhook-delivery@1` | tenant/subscription/destination-generation queue, circuit and concurrency isolated | bounded Product-authorized obligation backlog/attempts; stop destination only; explicit quarantine/expiry | durable delivery uncertainty under same identity/generation; Product contract owner controls inquiry/redrive | reconcile obligation, attempts and destination generation through `(R,F]`; original eligibility gates resume |
| `rel.telemetry-plane@1` | optional telemetry isolated from core, mandatory audit, tenant/source and data class | deterministically shed/reject optional data on bound/cardinality pressure; loss explicit; fair drain if accepted | missing optional telemetry is explicit loss, never evidence of business absence or success | recovered optional buffers are deduped/classified or discarded; never create authority; source generation gates resume |
| `rel.customer-telemetry-acceptance@1` | tenant/integration/source/generation acceptance and each historical/current-state/signal projection isolated from optional telemetry and transactional core | bound pre-acceptance intake without acknowledgement; after acceptance preserve durable backlog/checkpoints and stop new admission before overwriting accepted work; fair projection drain | identity, acceptance or projection uncertainty remains durable and attributable; Data/monitoring authority reconciles rather than dropping or guessing completeness | reconcile scoped observation identity, acceptance/projection watermarks, monotonic tokens, pending transition intents and relocation fence through `(R,F]`; only converged projections resume authoritative current-state use |
| `rel.mandatory-audit-plane@1` | mandatory audit separated from optional telemetry; tenant/subject/effect/source isolation | protected effect fails closed when durable audit responsibility cannot be admitted; no downgrade/overflow bypass | audit responsibility uncertainty blocks the joined protected effect; Security/Data authority owns disposition | restore audit/effect identity and governance through `(R,F]`; durable responsibility continuity gates effect admission |
| `rel.artifact-storage@1` | tenant/artifact/generation, transfer and governance pools isolated | bound upload/stream concurrency, bytes and leases; reject before false ready state; governance work reserved | metadata/object/lifecycle uncertainty remains explicit; artifact/governance owner reconciles | restore metadata/object/hash/lease plus erasure/hold/revocation through `(R,F]`; current releasability gates resume |
| `rel.reporting-derived@1` | tenant/report/workload queue/pool separated from live/recovery-critical capacity | bounded age/bytes/count, fair scheduling, checkpointed pause and explicit shed/expiry | derived incompleteness is disclosed and cannot become authoritative; owning report capability decides rebuild | discard/rebuild from authoritative source and generation; bounded backlog and dependency health gate resume |
| `rel.privileged-operations@1` | dedicated identity/runtime/egress/resource envelope by role and explicit target | strict target admission, reserved bounded recovery capacity, checkpoint/pause; reject outside policy | durable privileged operation state with authoritative inquiry and audit; ambiguity blocks retry | restore/recovery operation remains non-authoritative; current scope, target truth, audit and `(R,F]` evidence gate resume |

### Security/privacy, capacity/cost and evidence fields

| Profile key | `security_privacy` | `capacity_cost` | `evidence_requirements` |
|---|---|---|---|
| `rel.control-plane-placement@1` | authenticated scoped generations; tenant isolation; newer deny/fence wins; cached evidence cannot grant expansion | management QPS/concurrency, lease population, reconciliation backlog, tenant skew and recovery cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.cell-transactional-store@1` | tenant/cell separation, writer authority, governed data and audit/outbox atomicity preserved | transaction/connection/storage/ledger/recovery dimensions, skew and retry amplification measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.security-session-authority@1` | least privilege; current deny/revocation precedence; no cross-tenant/scope widening; missing evidence blocks | verification/cache/refill/revocation pressure and attack skew measured without weakening checks; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.placement-reference-cache@1` | authenticated scoped copy; no current-deny override; cache keys cannot cross tenant/generation | cache size/freshness/refill/origin concurrency and cold-start skew measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.performance-cache@1` | tenant/version keys and governed data classification; no auth or mutation authority | hit/miss, refill concurrency, origin load, memory/storage and hot-key skew measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.replay-consume-state@1` | tenant/source/epoch binding, least-privilege consume authority and immutable conflict evidence | ledger size/horizon, contention, replay skew and recovery scan cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.secret-key-authority@1` | namespace-bound identity/lease; no secret in ordinary state/evidence; rotation, revocation and crypto-erasure continuity | bootstrap/renewal concurrency, lease population, rotation overlap and outage pressure measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.configuration-authority@1` | signed/authorized schema-valid scope/generation; no permissive default; rollback cannot resurrect policy | distribution fanout, target count, convergence backlog, validation cost and rollout skew measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.outbox-publication@1` | trusted tenant/source envelope; payload classification retained; publisher cannot rewrite authority | backlog count/bytes/age, dispatcher concurrency, broker quota, drain and storage growth measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.broker-job-transport@1` | network/broker presence not trust; envelope/tenant/source/generation verified; scoped redrive | queue age/bytes/count, partitions abstractly, consumer concurrency, skew, retry and drain measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.consumer-inbox-effect@1` | tenant/source/content equivalence and effect authority verified; quarantine disclosure restricted | handler concurrency, attempt amplification, inbox/effect storage, poison pressure and dedup horizon measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.external-provider@1` | scoped credentials/egress, destination generation and hostile response/parser bounds; provider not authority | concurrency, rate/quota, latency, retry amplification, circuit probes, backlog and per-tenant/provider cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.realtime-fanout@1` | current subject/tenant/auth/placement binding; resume token not authority; cross-topic isolation | connections, fanout, buffer bytes, cursor work, reconnect storm and tenant skew measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.webhook-delivery@1` | Product gate, scoped secrets/egress, immutable tenant/subscription/destination generation and payload policy | per-destination concurrency, backlog age/bytes, attempts, response parsing and hostile destination cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.telemetry-plane@1` | telemetry not business authority; tenant/source/classification isolation; no secret/payload escalation; evidence provenance | intake/cardinality/buffer/bytes/storage/drop and tenant/source skew/cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.customer-telemetry-acceptance@1` | trusted observation namespace; tenant/integration/source/generation isolation; provider fields cannot weaken scope; classification/residency/retention preserved; current projection cannot grant authority beyond accepted data contracts | intake/acceptance/projection QPS, backlog age/count/bytes, storage/cardinality, checkpoint lag, replay/relocation work, tenant/source skew and cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.mandatory-audit-plane@1` | audit/effect identity and tenant/subject scope; immutable provenance; missing audit blocks; restricted evidence access | audit admission/durability/storage/cardinality and protected-effect pressure measured without downgrade; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.artifact-storage@1` | tenant/artifact/generation/hash binding; current revocation/erasure/hold precedence; scoped capabilities | bytes, objects, streams, integrity verification, lifecycle/recovery work and tenant skew/cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.reporting-derived@1` | tenant/source classification and purpose limitation; stale disclosure; optional result cannot authorize | queue age/bytes, compute/storage, fanout, skew, rebuild and runaway-work cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |
| `rel.privileged-operations@1` | least-privilege target-bound identity, separate runtime/egress/secrets, immutable audit and no AI authority | per-role/target concurrency, reserved recovery capacity, scan/backfill/egress and runaway cost measured; `CAPACITY-NUMERICS` | `E-4LEVEL(ALL-FAULT-VECTORS(profile_key))` |

### Fault, compatibility, blocker and OPEN fields

Each row below materializes profile-specific seed values. The complete `fault_vectors` and `release_blockers` fields SHALL be evaluated by `ALL-FAULT-VECTORS(profile_key)` and `ALL-RELEASE-BLOCKERS(profile_key)` above; therefore binding-derived and circuit-derived vectors necessarily add both evidence and their canonical blocker. The complete `open_decisions` field is the union of the profile-specific row and cross-profile selector. These joins are explicit for every `rel.*@version` key, not optional inheritance. Compatibility values use only the classes in `10-compatibility-and-change-classification.md`.

| Profile key | `profile_specific_fault_vectors` | `compatibility_class` | `profile_specific_release_blockers` | `profile_specific_open_decisions` |
|---|---|---|---|---|
| `rel.control-plane-placement@1` | `FV-CP-001`, `FV-CP-002`, `FV-REL-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-001`, `RB-REL-019`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-001`, `OPEN-REL-002`, `OPEN-REL-004`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.cell-transactional-store@1` | `FV-CELL-001`, `FV-CELL-002`, `FV-REC-001`, `FV-REC-002`, `FV-REL-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-002`, `RB-REL-003`, `RB-REL-018`, `RB-REL-019`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-003`, `OPEN-REL-004`, `OPEN-REL-013`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.security-session-authority@1` | `FV-SEC-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `behavior_breaking`, `recovery_breaking` | `RB-REL-004`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-027`, `OPEN-REL-028` |
| `rel.placement-reference-cache@1` | `FV-CP-002`, `FV-CACHE-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-001`, `RB-REL-005`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-001`, `OPEN-REL-002`, `OPEN-REL-015`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.performance-cache@1` | `FV-CACHE-001`, `FV-OVER-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `behavior_breaking`, `capacity_risk`, `conditionally_compatible` | `RB-REL-005`, `RB-REL-012`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-007`, `OPEN-REL-008`, `OPEN-REL-015`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.replay-consume-state@1` | `FV-ASYNC-003`, `FV-ASYNC-004`, `FV-REC-003`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking` | `RB-REL-010`, `RB-REL-011`, `RB-REL-018`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-015`, `OPEN-REL-025`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.secret-key-authority@1` | `FV-SECRET-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking` | `RB-REL-006`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-016`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.configuration-authority@1` | `FV-CONFIG-001`, `FV-CONFIG-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `conditionally_compatible` | `RB-REL-023`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-029`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.outbox-publication@1` | `FV-ASYNC-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-009`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-012`, `OPEN-REL-025`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.broker-job-transport@1` | `FV-ASYNC-001`, `FV-OVER-003`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-009`, `RB-REL-013`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-009`, `OPEN-REL-012`, `OPEN-REL-025`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.consumer-inbox-effect@1` | `FV-ASYNC-002`, `FV-ASYNC-003`, `FV-ASYNC-004`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking` | `RB-REL-010`, `RB-REL-011`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-012`, `OPEN-REL-025`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.external-provider@1` | `FV-EXT-001`, `FV-EXT-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `behavior_breaking`, `recovery_breaking`, `capacity_risk` | `RB-REL-007`, `RB-REL-008`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-005`, `OPEN-REL-006`, `OPEN-REL-007`, `OPEN-REL-008`, `OPEN-REL-011`, `OPEN-REL-014`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.realtime-fanout@1` | `FV-RT-001`, `FV-RT-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-014`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-017`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.webhook-delivery@1` | `FV-WH-001`, `FV-WH-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `product_gated`, `security_breaking`, `recovery_breaking`, `capacity_risk` | `RB-REL-015`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-018`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.telemetry-plane@1` | `FV-TEL-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-017`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-020`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.customer-telemetry-acceptance@1` | `FV-TEL-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-026`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-009`, `OPEN-REL-020`, `OPEN-REL-025`, `OPEN-REL-030`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.mandatory-audit-plane@1` | `FV-AUDIT-001`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-017`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-020`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.artifact-storage@1` | `FV-ART-001`, `FV-ART-002`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-016`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-019`, `OPEN-REL-025`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.reporting-derived@1` | `FV-OVER-002`, `FV-OVER-003`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `behavior_breaking`, `capacity_risk`, `conditionally_compatible` | `RB-REL-013`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-008`, `OPEN-REL-009`, `OPEN-REL-010`, `OPEN-REL-022`, `OPEN-REL-021`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |
| `rel.privileged-operations@1` | `FV-PRIV-001`, `FV-REC-003`, `FV-COMP-001`, `FV-EVID-001`, `FV-AI-001` | `security_breaking`, `recovery_breaking`, `behavior_breaking`, `capacity_risk` | `RB-REL-020`, `RB-REL-021`, `RB-REL-022`, `RB-REL-024` | `OPEN-REL-014`, `OPEN-REL-021`, `OPEN-REL-024`, `OPEN-REL-027`, `OPEN-REL-023`, `OPEN-REL-026`, `OPEN-REL-028` |

No catalog row may be inferred from a heading, vendor default, or runtime topology. A change to any key or field follows `10-compatibility-and-change-classification.md` and updates the semantic manifest, fault matrix, traceability and OPEN register together.

## Control Plane

### Fixed behavior

- Stable already-admitted tenant traffic MAY continue during Control Plane impairment only from a trusted, versioned, unexpired placement/reference path and only when the destination cell independently admits the same tenant/generation.
- Tenant lifecycle, suspension changes, relocation, new placement and other topology/authority changes fail closed without current Control Plane authority.
- A stale positive placement/lifecycle state cannot override a newer local/current deny, retired generation or recovery quarantine.
- Control Plane recovery reconciles post-`R` placement, suspension, revocation and governance state before protected/topology decisions resume.

### OPEN

Cache duration, replication/HA mechanism, regional topology, quorum, failover product and numeric availability targets.

## Cell transactional dependency

- Affected authoritative mutations fail closed when current transactional truth is unavailable.
- Cell failure does not route writes to another cell without an accepted placement/failover authority transition and stale-writer fence.
- Unrelated cells remain available subject to genuinely shared dependencies.
- Recovery starts non-authoritative and passes whole-cell `(R,F]` continuity gates before tenant traffic, schedulers or effectful workers resume.

Database HA product, replica/quorum topology, failover timers, storage sizing and RPO/RTO remain OPEN.

## Security/session/revocation authority

- New protected decisions fail closed when current authority cannot be established.
- Locally verifiable credentials may continue only under an explicitly accepted current-verification profile; cached/stale positive membership or permission is insufficient.
- Revocation/deny generations never regress through failover or restore.
- Reversing a deny is a separate current authorized/audited action, not a reliability fallback.

## Placement/performance/security caches

- Performance cache: bypass only to authoritative truth under stampede protection; otherwise degrade.
- Placement cache: versioned last-known-good within bound and destination admission; never overrides newer generation.
- Security acceleration cache: does not grant authority when freshness/current deny cannot be proved.
- Replay/correctness state: not disposable cache; loss fails closed or advances a trusted invalidating epoch.

Exact cache products, TTLs and invalidation transports remain OPEN.

## Secret/KMS authority

- No plaintext/default secret fallback.
- Only accepted bounded current leases may continue; a stale cached secret cannot defeat revocation/rotation policy.
- Secret outage affects only operations requiring that namespace; service identities remain least-privilege.
- Recovery must restore approved key authority or preserve intentional crypto-erasure.

## Configuration authority and distribution

- Configuration is a separate critical dependency from secret/key material. Its authority covers accepted content, schema, applicability scope, rollout generation and restore/rollback disposition.
- Missing configuration MAY use a verified last-known-good generation only when the profile explicitly permits it; malformed, unsigned/untrusted, contradictory, partially applied or scope-mismatched configuration fails closed for affected behavior.
- Configuration rollout SHALL be monotonic per governed scope. A lower generation, unknown field with unsafe semantics, or mixed generation outside an explicitly compatible matrix cannot become authoritative through restart, cache refill, failover or restore.
- A partial rollout is an explicit degraded state. Admission is bounded to the combinations declared compatible; affected mutations or privileged behavior stop when safety cannot be proven.
- Rollback SHALL NOT resurrect revoked authority, retired endpoints/sources, erased data access, unsafe retry policy or earlier governance decisions. Unsafe rollback requires forward recovery/reconciliation.
- Resumption requires one accepted configuration generation, mechanically validated content, target coverage evidence and disposition of nodes/cells/tenants that observed another generation.

Configuration store/product, distribution transport, schema tooling, rollout mechanism, cache horizon and numeric convergence targets remain OPEN.

## External providers and adapters

- Error mapping uses canonical Phase 11 failure classes.
- Timeouts, retry budgets, circuits and concurrency are scoped by tenant/integration/provider/destination as applicable.
- Stored provider-derived state is served only with explicit permitted staleness.
- Provider unavailability cannot create platform-wide retry storms or change canonical domain identity.
- Malformed, oversized, unauthenticated or semantically hostile provider data fails boundedly at the adapter.
- Ambiguous external effects reconcile by stable operation/provider identity.
- A compromised/untrusted provider cannot publish broader platform contract/tenant authority.

Any accepted provider integration remains an adapter instance; no provider product or version defines platform reliability semantics.

## Outbox and publication

- Authoritative fact and required outbox commit atomically.
- Broker outage pauses dispatch while durable outbox backlog remains bounded/admitted by policy.
- Retry republishes the same logical message identity and immutable semantic content.
- Publication acknowledgement uncertainty relies on consumer duplicate/content-integrity safety; it does not synthesize a new fact.
- Dispatcher cannot rewrite committed fact/audit evidence.

## Broker/job transport

- Transport availability controls progress, not business truth.
- No acknowledgement before durable consumer responsibility.
- Offset/receipt/visibility state is not canonical effect identity.
- Transport recovery reconciles process/inbox/effect state before progress changes.
- Queue outage/backlog recovery uses workload/tenant budgets and prevents synchronized redelivery collapse.

## Consumers, inbox and quarantine

- One logical executor/effect per trusted scoped message identity when duplicate-sensitive.
- Same identity requires equivalent immutable content; mismatch is integrity failure.
- Co-resident receipt/effect/result commits atomically; cross-authority effect uses stable outcome identity/reconciliation.
- Poison/unsupported work reaches governed quarantine after bounded policy.
- Redrive cannot bypass current authorization, placement, dedup, equivalence, generation or capacity admission.

## Realtime

- Realtime is advisory; authoritative writes and reads remain independent where dependencies permit.
- Gateway/fanout loss causes reconnect/resync, not business-state loss.
- Overload may reject new connections/subscriptions or shed non-authoritative detail under a declared profile.
- Current authorization, replay uniqueness/continuity and placement generation remain mandatory under pressure.
- Stale/revoked/source-retired subscriptions stop; resume/cursor does not restore authority.
- Reconnect storms are isolated and admitted by tenant/principal/connection budgets.

Phase 12 owns connection/health SLIs, signals and alerting; Phase 13 owns runtime/fanout topology.

## Outbound webhooks

Outbound webhook families remain Product-gated. When a profile is accepted:

- originating business fact does not roll back because a destination is slow/down;
- attempts are isolated per tenant/subscription/destination generation;
- same delivery ID retains immutable contract/source/scope/payload meaning and bound destination generation;
- destination change never retargets an old obligation;
- ambiguous attempt reconciles; at-least-once redelivery remains possible only under the original eligible generation;
- retired generation leads to fence/cancel/quarantine or a new caused delivery identity under Product policy;
- SSRF, response-size, redirect, concurrency and secret rules remain mandatory.

Exact signature, egress mechanism, retry numerics and Product cancellation/reissue policy remain OPEN.

## Artifacts and object storage

- Transactional metadata/generation remains release authority; object presence alone is not availability.
- Upload/finalize, delivery lease and erasure use accepted generation/fencing semantics.
- Storage outage leaves explicit preparing/unavailable/reconciliation state; no false ready/erased success.
- Download/release rechecks current authorization/releasability and generation before protected bytes.
- Active streams and late lease admission are reconciled/fenced before confirmed erasure.
- Object/metadata mismatch is unavailable/quarantined, never guessed.
- Legal hold/governance uncertainty blocks destructive deletion; erasure uncertainty blocks re-exposure.

## Telemetry plane

- Optional telemetry pressure/outage cannot exhaust transactional core or the mandatory-audit path.
- Optional telemetry uses the `rel.telemetry-plane` profile and deterministically sheds/rejects under unavailable or saturated intake; missing telemetry is never fabricated completeness.
- Customer monitoring observations use the separate `rel.customer-telemetry-acceptance` profile. Acknowledgement occurs only after canonical scoped identity and durable responsibility exist. Optional-loss policy ends at that boundary; accepted observations, projection checkpoints and pending transition/signal intents remain discoverable and replayable.
- Historical projection, monotonic current-state projection and durable transition/signal projection consume the same accepted observation identity. Downstream outage creates bounded durable lag; duplicate or out-of-order delivery cannot regress current state or lose an already-committed transition obligation.
- Relocation/failover selects one authoritative acceptance source generation for new observations and reconciles acceptance/projection watermarks before target admission; source and target cannot both accept the same generation as new authority.
- Mandatory audit uses the separate `rel.mandatory-audit-plane` profile. When durable audit responsibility is part of an accepted protected-effect boundary, inability to establish it fails that affected effect closed; optional telemetry loss policy cannot override or downgrade it.
- Buffering is bounded and durable only where the selected profile explicitly requires it.
- Ordering/dedup identity is scoped by trusted tenant/integration/source/generation.
- Current-state transitions and required signals retain accepted atomic/recoverable advancement semantics.
- Raw volume is not forced through the general event broker.

Exact optional and customer-telemetry stores, durable acceptance mechanism, buffers, retention, projection topology and loss/backpressure thresholds remain OPEN; their distinct acceptance semantics do not.

## Reporting, AIOps and derived workloads

- Separate pool/queue/concurrency from core transactional and security/recovery work.
- May delay, shed or enter brownout when Product contract permits.
- Cannot silently become authority for identity, authorization, tenant placement, retry/recovery eligibility, release or incident closure.
- Derived rebuilds use isolated generation and cannot erase production dedup/current projection truth.

## Automation, parsers, SQL, admin, migration and recovery

- Use smaller trust envelopes, explicit target scope, resource/time/output/egress bounds and current authority.
- Dangerous execution does not share the primary API worker pool or unrestricted credentials.
- Timeout/termination does not prove external/destructive effect absence.
- Recovery/admin priority cannot bypass tenant, audit, governance or idempotency gates.
- A generic platform admin/network position is not unrestricted cross-tenant authority.

Phase 13 defines runtime isolation mechanisms; Phase 15 defines runbook/break-glass procedure.

## Cell/region failure preparation

- Cell is the normal operational blast-radius unit.
- Second-cell addition does not change API/event/business identities.
- Cell failure/failover/relocation uses current placement generation, source fencing and target admission.
- Regional hierarchy, active-active/passive and residency topology remain OPEN until Product/compliance/capacity evidence.
- No contract assumes global synchronous dependency merely for convenience.
