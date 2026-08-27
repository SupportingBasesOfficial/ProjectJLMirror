# Zabbix Monitoring Source — Provider Adapter Contract

**Status:** proposed baseline
**Instantiates:** ADR-013 (External Provider Adapter Architecture), `provider-callback-and-ingress-contracts.md`, `docs/07-system-design/realtime-cache-and-provider-boundaries.md`
**Drivers:** `FR-MON-001..006`, `FR-OPS-001..002`

## Purpose

`docs/01-product/product-definition.md` names Zabbix as JLMIRROR's initial Monitoring Source, and ADR-013 explicitly anticipates it ("Initial Monitoring Source support MAY include Zabbix, but Zabbix concepts SHALL NOT become the only canonical Monitoring model"). Neither document fixes Zabbix's concrete API version, authentication mechanism, polling cadence, or trust model — those are exactly what this contract supplies. This document is a **provider-specific instantiation**, not a new architecture decision: every trust/atomicity/normalization rule below is inherited unchanged from ADR-013 and `provider-callback-and-ingress-contracts.md`; this document only fixes Zabbix's concrete values inside that already-accepted frame.

This contract does not itself authorize `impl.provider-integration@1` implementation — per `docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md:34`, that slice is `deferred_product_gated` until "exact Product/domain + provider trust/auth/reconciliation contract is accepted." Accepting this document is what supplies the missing half of that gate for Zabbix specifically; the Monitoring domain/API endpoint contracts remain a separate, still-open prerequisite.

## Integration model: authenticated pull, webhook as untrusted hint only

ADR-013:48 requires that when a provider "cannot offer a callback authentication mechanism strong enough for the feature threat model," the integration "must instead use an explicitly reviewed weaker-trust design — for example treating the callback as a hint followed by an authenticated provider read/reconciliation." Zabbix's outbound "Action" webhook mechanism has no standard signing/authentication scheme (payload shape and any shared-secret header are entirely operator-scripted per Zabbix instance, not a protocol JLMIRROR can rely on as strong authentication). This contract therefore selects the weaker-trust design explicitly, rather than granting an unauthenticated callback trusted-command authority:

```text
Zabbix instance
  -> (A) scheduled authenticated poll (source of truth, always runs)
  -> (B) optional Action webhook -> POST /callbacks/v1/zabbix/{integration_reference}
         treated ONLY as: "poll this tenant/source sooner than the next scheduled cycle"
         never treated as: "this problem/event happened" on its own authority
  -> authenticated Zabbix API read confirms/normalizes actual current state
  -> normalized platform resource/metric/observation/problem/health concepts
```

Path (A) is mandatory and is what makes the integration correct on its own; path (B) is a pure latency optimization that can be disabled per tenant/instance without any loss of correctness — this resilience property follows directly from ADR-013's weaker-trust-design rule quoted above, not from `FR-MON-004` (that requirement governs cross-tenant blast-radius containment specifically: "a failing tenant source does not block unrelated tenant progress," `docs/02-requirements/functional-requirements.md:47` — it is invoked correctly below, where one tenant's behavior must not affect another's). This design keeps `impl.customer-telemetry@1`'s durable-acceptance boundary (see the companion `OPEN-REL-030` decision record) as the only authority that actually accepts an observation — the webhook never writes accepted state directly.

## (A) Authenticated poll — source of truth

### Authentication

Zabbix API tokens (Zabbix 5.4+, `user.login`-free token auth) are the required credential mechanism. Username/password session login (`user.login` returning a session `auth` string) SHALL NOT be used: sessions expire and require credential re-presentation on a schedule outside JLMIRROR's control, which is a weaker, harder-to-audit credential lifecycle than a long-lived, individually revocable API token scoped to a dedicated JLMIRROR integration user with the minimum required Zabbix permission (read-only on hosts/items/triggers/problems/events for the mapped host groups; JLMIRROR SHALL NOT request Zabbix administrative/write scope for the Monitoring read path).

The API token is a secret and follows `secret_manager_kms` handling (Wave 1 residual C2, `implementation/wave-1/IMPLEMENTATION_MANIFEST.json:26-38|residual_c2_choices_not_selected`) — never logged, never returned in any JLMIRROR API response, stored only through the accepted secret-manager mechanism once selected.

### Endpoints and polling shape

JSON-RPC 2.0 over HTTPS against the tenant-configured Zabbix API URL (`<zabbix-base>/api_jsonrpc.php`), using only:

- `host.get` — resource inventory (bounded to configured host groups);
- `item.get` — metric definitions and latest/current value only (`lastvalue`/`lastclock`) — **not** a source of historical samples;
- `history.get` — the actual `metric_observation` history stream, bounded incremental retrieval per item via `time_from`/cursor, with Zabbix's per-value-type history tables (float/unsigned/string/text/log) each queried explicitly since Zabbix does not expose a single unified history call across value types;
- `trigger.get` — problem/health definitions;
- `problem.get` — active problems (polled on the tightest cadence of the four);
- `event.get` — historical event stream, bounded by `eventid`/time-range cursor for incremental sync.

`item.get`'s `lastvalue`/`lastclock` feeds the Tier 1 current-state compare-and-set (see ordering token below) cheaply on every cycle; `history.get` is the only endpoint that can actually populate the `metric_observation` history required by `FR-MON-005`'s metric-history surface and the canonical identity mapping below — omitting it would leave the canonical `itemid`+`clock`+`ns` → `metric_observation` mapping with no corresponding retrieval mechanism.

Exact polling interval per endpoint is `OPEN` pending production capacity evidence (per `docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md` numeric-threshold discipline — this contract fixes the mechanism, not the number); the mechanism SHALL support an independently configurable interval per endpoint class (problems polled tighter than inventory) and per tenant, so one tenant's interval cannot starve another (`FR-MON-004`).

### Canonical identity mapping

Per `docs/08-data/telemetry-plane.md`'s canonical identity rule and `FR-MON-006`, Zabbix's own IDs are retained only as external references inside a JLMIRROR-derived `observation_identity_scope`:

```text
observation_identity_scope = (tenant_id, monitoring_source_id, "zabbix", zabbix_instance_generation)
```

| Zabbix concept | Zabbix native ID (external reference only) | Platform canonical concept |
|---|---|---|
| Host | `hostid` | `monitoring_resource` |
| Item | `itemid` | `metric_definition` |
| Trigger | `triggerid` | contributes to `health-projections` |
| Problem | `eventid` (problem-class event) | `problem` |
| History value | `itemid` + `clock` + `ns` | `metric_observation` |

`zabbix_instance_generation` exists because a tenant can reconfigure or replace a Zabbix instance pointing at the same `monitoring_source_id`; per `telemetry-plane.md`'s ordering-semantics rule, a reconnect/reconfiguration that can invalidate `eventid`/`clock` comparison introduces a new generation rather than reusing an ambiguous counter domain. A raw `hostid`/`itemid`/`eventid` from one generation or one tenant's instance MUST NOT be treated as comparable to the same numeric ID from another generation or another tenant's instance — Zabbix IDs are small sequential integers scoped only to a single Zabbix instance and collide constantly across independent instances.

The generation counter is **not** automatically advanced by ordinary reconfiguration that cannot itself change which physical instance is being addressed (credential rotation, host-group scope edit) — those remain the same generation. A change to the Zabbix **base URL** is different in kind and is deliberately excluded from "ordinary reconfiguration": a URL change is inherently ambiguous — it MAY be a genuine instance replacement, or a same-instance correction (IP change, reverse-proxy/DNS migration). Because that ambiguity is exactly the failure mode this mechanism exists to prevent, the platform SHALL NOT accept a bare base-URL edit through the ordinary "edit monitoring source configuration" path at all: any base-URL change SHALL be rejected there and SHALL require going through the explicit, distinct "replace monitoring source instance" action instead, mirroring the same "explicit governed action" discipline already established for redrive (`implementation/wave-2/README.md`, "Redrive is an explicit governed action"). This forces even a legitimate same-instance URL correction through the deliberate confirmation step, which is the correct trade (a rare extra confirmation click) against the alternative (an operator's ordinary URL edit silently reusing a generation that may now point at a different, colliding dataset). The platform SHALL NOT infer a generation change from any other API-level signal alone (e.g. a token change, or `hostid`/`itemid` sequences appearing to reset), because those signals cannot reliably distinguish "same instance, credential rotated" from "different instance, coincidentally similar configuration." An operator who replaces a Zabbix instance without invoking the explicit action produces silently colliding identity across the old and new instance's overlapping IDs — this residual risk is inherent to any provider whose native IDs are small per-instance integers and is mitigated by, not eliminated by, requiring an explicit action rather than trusting inference.

The current-state ordering token is `(zabbix_instance_generation, clock, ns)` with `itemid`/`eventid` as a final deterministic tie-break for exact-equal timestamps — **not** a platform-assigned acceptance ordinal. This matters because acceptance order and source chronology are different things: during backfill, retry, relocation, or out-of-order pagination, an older sample can be *accepted* by the platform after a newer sample already advanced current state. An ordering token based on acceptance time would let that late-arriving older sample win the compare-and-set purely because it was processed later — silently regressing current state with stale data, which `telemetry-plane.md`'s monotonic-projection invariant forbids. Ordering on source chronology instead means an old sample's `clock`/`ns` correctly loses to an already-applied newer one regardless of when the platform happened to accept it. This matches `telemetry-plane.md`'s own preference order for ordering tokens ("a provider sequence combined with an explicit source generation/epoch when the provider can reset counters," `telemetry-plane.md:103`) over the platform-acceptance-ordinal fallback, which that same document reserves for cases "when provider ordering is insufficient" (`telemetry-plane.md:104`) — here it is not: `clock`+`ns` scoped to `zabbix_instance_generation` is sufficient, precisely because the generation boundary (see above) is what makes a reused/reset Zabbix clock domain safe to compare within. `clock`+`ns` remains `observed_at` per `telemetry-plane.md`'s definition and is not, by itself, a claim of wall-clock accuracy (provider clocks can still skew relative to true time) — only that it is internally comparable within one generation, which is all monotonic current-state compare-and-set requires.

### Outbound connector requirements (ADR-013)

- connect/request/overall timeouts: bounded, per-tenant configurable, `OPEN` numeric value pending evidence;
- retry: bounded, exponential backoff, only for retryable Zabbix API error classes (never blind-retry a request whose effect is ambiguous — read-only `*.get` calls have no side effect so this is naturally simpler than the write-path atomicity rules in ADR-008, but the *durable-acceptance* step downstream of the read still follows ADR-008 in full);
- SSRF/egress: the tenant-configured Zabbix base URL is validated against the platform's accepted outbound connector allow/deny policy before every poll cycle, not only at configuration time (an operator changing DNS after configuration SHALL NOT bypass egress policy);
- response body size limit: bounded, sized to the largest legitimate `problem.get`/`event.get`/`history.get` page for the configured pagination window;
- rate limit: bounded per tenant/source so one tenant's misconfigured or oversized Zabbix instance cannot consume shared polling-worker capacity (`FR-MON-004`);
- circuit breaker: a tenant/source whose Zabbix instance is repeatedly unreachable or repeatedly authentication-failing enters the degraded-state policy from ADR-013 rather than retrying at full cadence indefinitely; sync-operation status (`monitoring-sync-operations` per `docs/09-api-contracts/domain-api-surface-map.md`) SHALL reflect this so operators see "not syncing" rather than silence.

## (B) Webhook hint path

### Ingress

`POST /callbacks/v1/zabbix/{integration_reference}`, inheriting every canonical HTTP framing and post-auth parse-limit rule from `provider-callback-and-ingress-contracts.md` unchanged. Per that document's mandatory closure requirement ("Provider profiles define a concrete maximum raw-body size before implementation/release. If not yet measured/accepted, the value is explicitly `OPEN`; unlimited callback bodies are prohibited," `provider-callback-and-ingress-contracts.md:66`), Zabbix's own raw-body limit is `OPEN` — see "Open items" — precisely because Zabbix webhook bodies are operator-scripted per instance rather than protocol-fixed, so no other provider's default is safe to inherit silently here.

### Trust boundary

Because Zabbix's webhook body/headers are operator-scripted per instance rather than protocol-defined, this endpoint SHALL NOT be treated as an authenticated Zabbix callback under `provider-callback-and-ingress-contracts.md`'s "Authentication/freshness/replay ordering" section. Instead it follows that same document's "Weakly authenticated providers" fallback pattern exactly:

```text
untrusted webhook POST
  -> tenant/source resolved ONLY from {integration_reference} (trusted, path-bound lookup) — never from payload content
  -> bounded trigger/hint only: payload content, once tenant/source is already fixed, is read only to
     select which HOST within that already-resolved tenant/source to prioritize; never trusted as a
     fact about problem/resource state, and never able to select or redirect to a different tenant/source
  -> schedule an out-of-cycle authenticated poll (path A) for that resolved tenant/source, bounded by
     the same per-tenant rate limit as ordinary polling
  -> the resulting authenticated read is what may become an accepted observation
```

This is a direct restatement of the inherited base contract's "Tenant binding" rule (`provider-callback-and-ingress-contracts.md:42-56`): tenant/integration identity is resolved from trusted configured state after locating the callback, and payload fields "are treated as untrusted provider data... They cannot reroute the callback to another tenant." The `{integration_reference}` path segment is opaque lookup input only (per that same document's "Opaque callback reference" rule) — possession of the URL grants no mutation authority; it identifies which tenant/source to poll sooner, and payload content may narrow that to a specific host within it, never widen or redirect it.

### Abuse resistance

A webhook endpoint with no strong authentication is an amplification target: an attacker who obtains or guesses `{integration_reference}` could otherwise force unbounded extra polling against a tenant's Zabbix instance. The out-of-cycle poll this endpoint triggers SHALL be coalesced/debounced per tenant/source (repeated hints within a bounded window trigger at most one extra poll, not one per request; exact window value is `OPEN`, see "Open items") and SHALL count against the same per-tenant rate limit as scheduled polling, not an unbounded separate budget. Coalesce/debounce state SHALL be shared and durable across every ingress/worker instance in the fleet — a per-process-only debounce would let the "at most one extra poll per window" bound be multiplied by the number of instances receiving traffic, even though the per-tenant rate limit still ultimately caps the result.

This section governs only per-tenant/source abuse. Protection against a coordinated actor triggering many *different* tenants' valid `{integration_reference}` values simultaneously (aggregate fleet-capacity fan-out) is a general, cross-cutting concern already owned by `OPEN-REL-008` (bulkhead/concurrency isolation), `OPEN-REL-009` (bounded/attributable backlog with overflow behavior) and `OPEN-REL-010` (fairness protecting unrelated tenants) — inherited by every capability including this one, not reinvented here.

## Testing

In addition to every test already required by `provider-callback-and-ingress-contracts.md` for the webhook path:

- a poll cycle with zero configured webhook activity still converges all state within the configured interval (proves path A is sufficient alone);
- disabling the webhook entirely for a tenant does not change eventual correctness, only latency;
- a webhook hint for a tenant/source under an active circuit-breaker degraded state does not bypass the degraded-state policy;
- `hostid`/`itemid`/`eventid` reused across two different `zabbix_instance_generation` values (simulating instance replacement) are proven to project as independent platform entities, not merged;
- a burst of duplicate/rapid webhook hints for the same tenant/source produces at most one bounded out-of-cycle poll, not one per request;
- Zabbix API token rejected/expired mid-cycle surfaces as a degraded `monitoring-sync-operations` state, not a silent stall or a crash that loses in-flight normalization;
- egress policy is re-validated on every poll cycle, not cached indefinitely from configuration time;
- `history.get` is actually invoked and its results reach `metric_observation` storage — a poll cycle that only exercises `item.get` MUST NOT be treated as sufficient to satisfy `FR-MON-005`'s metric-history surface;
- editing the monitoring source configuration through the ordinary path with a changed base URL is rejected/blocked, not silently accepted as same-generation;
- an older sample (earlier `clock`/`ns` within the same `zabbix_instance_generation`) accepted *after* a newer sample was already applied does not regress the current-state projection, simulating backfill/retry/relocation/out-of-order-pagination delivery order.

## Open items

- Exact polling interval per endpoint class and per accepted plan/tier: `OPEN`, pending capacity evidence (Phase 11 numeric-threshold discipline).
- Exact webhook-hint coalesce/debounce window: `OPEN`, pending capacity evidence.
- Exact webhook raw-body maximum size: `OPEN` — per `provider-callback-and-ingress-contracts.md:66`'s mandatory per-provider closure requirement, this MUST be fixed to a concrete evidenced value (or remain explicitly `OPEN`, never silently inherited from another provider's default) before implementation/release.
- Secret storage mechanism for the Zabbix API token: depends on `secret_manager_kms` (Wave 1 residual C2), not yet selected.
- Whether Zabbix's `problem.get` acknowledgement/severity/tag fields map 1:1 into JLMIRROR's `problem`/`health-projections` concepts or require a richer intermediate model: deferred to Monitoring domain/API contract design, out of scope for this provider-trust contract.
