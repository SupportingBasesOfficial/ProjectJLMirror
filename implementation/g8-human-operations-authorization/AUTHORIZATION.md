# G8 Human Operations — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@be9d2a2fe49c308d4d8c9ca06e9ebafbb4ae69f8`  
**Authorization ID:** `g8.human-operations@1`

## Purpose

Authorize only the eighth AI-E2E product increment: tenant-safe human operational accountability over canonical Monitoring resources and G7 Alerts.

G8 closes this bounded path:

```text
current canonical Alert / Monitoring resource
 -> explicit responsible-principal assignments
 -> explicit current-action assignment/projection
 -> actor-attributed Alert ACK
 -> authoritative platform-native visibility requirement
 -> immutable visibility receipt
 -> protected human-operations API+BFF/UI
 -> derived chronological timeline
```

G8 does **not** authorize external notification dispatch, provider delivery state, WhatsApp/email/SMS/Teams/Slack adapters, generic response/waiting workflows, approvals/budget, escalation automation, ITSM, provider write-back, Alert lifecycle mutation or production activation.

## Authorization on acceptance

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g8_human_operations_only
merge_authorization = not_granted
```

## Dependencies

G8 depends on:
- canonical G1 identity/tenant/current-authorization foundation;
- canonical G3 Monitoring Resource identity;
- canonical G7 Alert policy/lifecycle implementation;
- issue #149 and `docs/00-foundation/project-memory/HUMAN-OPERATIONS-MODEL.md`;
- organization/access authority as identity/scope source, without expanding that authority here.

## Orthogonal dimensions

G8 MUST preserve:

```text
ALERT_LIFECYCLE != RESPONSIBILITY
RESPONSIBILITY != CURRENT_ACTION_OWNER
CURRENT_ACTION_OWNER != ACKNOWLEDGER
VIEWER != ACKNOWLEDGER
ACKNOWLEDGEMENT != ALERT_RESOLUTION
RESOURCE_RESPONSIBILITY != ALERT_ACTION_ASSIGNMENT
VISIBILITY != DELIVERY
VISIBILITY != RESPONSE
NOTIFICATION_RECIPIENT != RESPONSIBLE_PERSON
PROVIDER_ACK != JLMIRROR_ACK
TIMELINE != MUTABLE_BUSINESS_TRUTH
```

No single giant `status` may encode these dimensions.

## Resource responsibility v1

G8 may introduce tenant-owned responsibility assignments for a canonical Monitoring Resource.

An assignment MUST pin:
- opaque `responsibility_assignment_id`;
- `tenant_id`;
- canonical `monitoring_resource_id`;
- stable platform `principal_id`;
- bounded `responsibility_role`;
- `effective_from` and optional `effective_until`;
- assigning actor;
- assignment source/reason code;
- immutable creation/equivalence evidence.

Multiple principals MAY be concurrently responsible for one resource.

The only admitted v1 responsibility roles are:

```text
technical_responsible
service_owner
operator
customer_responsible
```

The only admitted v1 assignment sources are `manual | configured`.

Assignment identity/content is immutable. Ending an assignment is a one-way terminal closure that MUST record the ending actor, effective-until time and bounded end reason; a closed assignment cannot be reopened.

Responsibility does not grant permission by itself. Current authorization remains separately required for every action.

Free-form names, provider user IDs, email addresses or phone numbers MUST NOT become responsibility identity.

## Alert current-action assignment v1

G8 may introduce explicit Alert action assignments, historically reconstructable through effective intervals.

Exactly one current action owner MAY be selected for one active Alert at a time.

The action owner MUST be a stable platform principal and MUST be separate from resource responsibility.

The only assignable v1 action kinds are:

```text
investigate_alert
acknowledge_alert
review_alert
customer_review_required
```

`no_human_action_required` is projection-only and MUST NOT create a fake assignment or owner.

Action-assignment identity/content is immutable. Reassignment is an atomic one-way closure of the prior current assignment plus creation of the successor, with the closing actor/reason retained. A closed assignment cannot be reopened.

The persisted assignment fact is authoritative. The current-action projection is derived from those facts and MUST NOT become an independently writable source of truth.

G8 does not authorize escalation policy/timers or SLA clock ownership.

## ACK v1

ACK is an immutable actor-attributed business fact, never a boolean-only mutation.

An ACK MUST pin:
- opaque `acknowledgement_id`;
- exact `tenant_id + alert_id`;
- acknowledging `principal_id`;
- acknowledgement timestamp;
- bounded authority/scope snapshot;
- optional bounded note/reason;
- idempotent logical action identity/equivalence evidence.

Only a current, authorized principal may ACK an active Alert.

ACK MUST NOT:
- resolve or reopen an Alert;
- imply responsibility;
- imply current-action ownership;
- imply notification delivery;
- imply view by another principal.

Unacknowledge is not authorized in G8.

## Authoritative visibility v1

G8 may introduce only a JLMirror-controlled, authenticated visibility/confirmation path.

A visibility requirement MUST pin:
- opaque `visibility_requirement_id`;
- exact tenant and protected subject;
- required viewer principal;
- viewer side `internal | customer`;
- capability class `platform_native_authenticated_view@1`;
- protected presentation/reference identity;
- creation actor/time and immutable equivalence evidence.

A visibility receipt MUST be immutable and pin:
- exact requirement;
- authenticated viewer principal;
- observed-at timestamp;
- current tenant/session/authorization evidence sufficient for audit;
- idempotent receipt identity/equivalence evidence.

A new Alert visibility requirement may be created only while that Alert is active/current. If a requirement already existed before the Alert resolved, a later receipt MAY still be recorded as late evidence for that exact requirement. Such late evidence MUST NOT reopen, resolve or otherwise mutate the Alert lifecycle, current action assignment or notification state.

For this admitted capability class only, the system may derive:

```text
not_viewed_yet = requirement exists AND no authoritative receipt exists
viewed = at least one authoritative receipt exists
```

This derivation is valid only because the required protected content is admitted through the instrumented JLMirror-native confirmation surface.

G8 MUST NOT infer external-channel viewing or delivery. External communication/channel capability classes belong to G9.

## Current-action projection v1

The projection may answer:
- who must act now;
- bounded next-action kind;
- why that action is current;
- which Alert/resource facts it derives from;
- current projection revision/evidence time.

It MUST be recomputable from authoritative G8 facts and current G7 Alert state.

It MUST NOT silently synthesize:
- notification delivery;
- customer response;
- approval state;
- ticket ownership;
- escalation state;
- Alert lifecycle.

## Timeline v1

G8 may expose a chronological timeline composed from immutable/terminally-closed authoritative facts:
- resource responsibility assignment start/end;
- Alert action assignment start/end;
- ACK;
- visibility requirement;
- visibility receipt.

Current-action projection values MAY be displayed alongside the timeline as derived state, but projection changes are not timeline authority.

The timeline is read-only/derived. It is not a seventh mutable business source.

## Exact persistence authority

The future G8 SQL migration may create only:

```text
human_operations.resource_responsibility_assignment
human_operations.alert_action_assignment
human_operations.alert_acknowledgement
human_operations.visibility_requirement
human_operations.visibility_receipt
human_operations.current_action_projection
```

All six relations MUST use tenant RLS + FORCE RLS.

Application executable code MUST NOT receive direct table mutation authority. Effectful mutation must pass guarded database capabilities or an equivalently closed authority boundary proven by conformance.

No additional `human_operations.*` business-state relation is authorized.

## Read/API/UI authority

G8 may add protected:
- resource responsibility list/current view;
- Alert ACK evidence;
- Alert current-action owner;
- internal/customer native visibility state;
- bounded human-operations timeline;
- assignment/ACK/visibility action surfaces.

The UI MUST distinguish dimensions instead of rendering a giant status.

## Explicit non-authority

G8 does not authorize:
- Alert create/resolve/reopen or policy evaluation changes;
- unacknowledge;
- suppression;
- notification intent;
- dispatch/provider acceptance/delivery attempts or delivery state;
- external-channel read receipts;
- WhatsApp/email/SMS/Teams/Slack integrations;
- generic response/waiting state;
- budget/quote/approval workflow;
- escalation/routing automation;
- ITSM incident/ticket/task behavior;
- Automation/AIOps mutation;
- provider write-back;
- public webhook/realtime mutation authority;
- production/C3 activation.

## Required implementation-path governance

Future implementation PR:
- branch prefix: `impl/g8-human-operations`;
- required label: `jlmirror-slice:g8-human-operations`;
- claim: `implementation/g8-human-operations/IMPLEMENTATION_CLAIM.json`;
- exact SQL: `sql/human_operations/001_human_operations.sql`;
- runtime workflow: `.github/workflows/g8-human-operations-runtime.yml`;
- same repository and current default-branch base required.

## Required proof

The implementation MUST prove at minimum:
- multiple resource responsible principals remain distinct from action owner;
- ACK actor/time/authority and idempotency;
- ACK does not alter G7 Alert lifecycle;
- concurrent action-owner replacement has one current owner and complete history;
- cross-tenant assignment/ACK/view attempts fail closed;
- resolved/non-current Alert cannot gain new ACK/action authority;
- native visibility `not_viewed_yet -> viewed` derives only from admitted authoritative receipts;
- viewer and acknowledger may differ;
- external delivery/view state is absent, not fabricated;
- direct application table writes are blocked;
- tenant RLS/FORCE RLS and privileged-owner closure;
- protected HTTP/BFF/UI journey;
- replay/concurrency/recovery semantics;
- hardened runtime/container proof.

## Gate laws

```text
G8_AUTHORIZED != G9_AUTHORIZED
ACKNOWLEDGEMENT != ALERT_LIFECYCLE
RESPONSIBILITY != AUTHORIZATION
RESPONSIBLE_PERSON != CURRENT_ACTION_OWNER
VIEWER != ACKNOWLEDGER
NATIVE_VISIBILITY != EXTERNAL_DELIVERY
NO_EXTERNAL_RECEIPT != NOT_VIEWED
TIMELINE != SOURCE_OF_TRUTH
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
