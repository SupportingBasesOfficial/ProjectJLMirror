# G9 Notification + Delivery — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@a264e17852bfd114546438ee9094c7655c920839`  
**Authorization ID:** `g9.notification-delivery@1`

## Purpose

Authorize only the ninth AI-E2E product increment: one tenant-safe notification channel from explicit notification intent through provider dispatch and delivery evidence.

G9 v1 closes:

```text
current admitted Alert / human-operations context
 -> immutable notification intent
 -> durable dispatch outbox
 -> WhatsApp adapter attempt
 -> provider acceptance/delivery evidence
 -> callback inbox/dedup
 -> derived delivery projection
 -> protected read/UI
 -> retry/reconciliation/fallback-required presentation
```

## First channel

The only admitted transport channel in G9 v1 is:

```text
whatsapp_business@1
```

The domain remains provider-neutral. Provider-specific message IDs and callback IDs are evidence references only and MUST NOT become platform notification identity.

Email, SMS, push, Teams, Slack and additional WhatsApp/provider implementations are outside this authorization.

## Core state separation

G9 MUST preserve:

```text
NOTIFICATION_INTENT != DELIVERY_ATTEMPT
DELIVERY_ATTEMPT != PROVIDER_EVIDENCE
SENT != PROVIDER_ACCEPTED
PROVIDER_ACCEPTED != DELIVERED
DELIVERED != VIEWED
EXTERNAL_READ != G8_AUTHORITATIVE_VIEW
NOTIFICATION_RECIPIENT != RESPONSIBLE_PERSON
NOTIFICATION_RECIPIENT != CURRENT_ACTION_OWNER
PROVIDER_MESSAGE_ID != NOTIFICATION_INTENT_ID
PROVIDER_CALLBACK_ID != PLATFORM_EVIDENCE_ID
NOTIFICATION_STATE != ALERT_LIFECYCLE
NOTIFICATION_STATE != ACKNOWLEDGEMENT
TIMELINE != MUTABLE_BUSINESS_TRUTH
```

## Notification intent v1

An intent is immutable and MUST pin:
- opaque `notification_intent_id`;
- tenant;
- exact protected subject, initially one G7 Alert;
- recipient platform principal when known;
- protected destination reference;
- channel class `whatsapp_business@1`;
- bounded notification reason;
- immutable payload/template reference and content hash;
- optional G8 native visibility requirement reference;
- creating actor/time/current-authority evidence;
- idempotent logical action identity/equivalence evidence.

The only admitted reasons are:

```text
alert_requires_attention
alert_action_requested
customer_awareness_required
```

Creating an intent MUST NOT mutate Alert lifecycle, ACK, responsibility or current-action ownership.

## Dispatch/attempt v1

Dispatch is worker-owned and at-least-once safe.

Each attempt MUST have:
- opaque `notification_attempt_id`;
- exact intent;
- attempt number;
- immutable dispatch request evidence;
- adapter/channel version;
- started/completed timestamps;
- normalized terminal attempt outcome;
- optional provider message reference;
- bounded failure class;
- idempotent dispatch identity.

Attempt outcomes are:

```text
dispatching
sent
provider_accepted
delivered
failed
unknown
```

A later provider callback may advance evidence to a stronger state but MUST NOT rewrite historical attempts.

## Provider evidence v1

Provider callbacks/evidence are append-only and normalized into:

```text
provider_accepted
delivered
external_read_observed
failed
unknown
```

Raw provider payloads must be bounded, privacy-minimized and retained only as the minimum audit/provenance envelope required by the implementation.

External read evidence is supplementary. It MUST NOT satisfy a workflow that requires authoritative awareness unless that workflow separately terminates on the admitted G8 platform-native authenticated visibility requirement/receipt.

## Callback inbox v1

Provider callbacks MUST enter through a canonical HTTP callback boundary with:
- signature/authenticity verification before business effects;
- bounded payload and timestamp/replay window;
- tenant/channel routing derived from trusted configuration, not payload assertion alone;
- durable callback idempotency;
- duplicate suppression;
- out-of-order evidence reconciliation;
- poison/quarantine behavior for malformed or unbindable callbacks.

A callback must never gain Alert, ACK or responsibility mutation authority.

## Delivery projection v1

The projection may answer:
- current normalized delivery state;
- last attempt;
- latest provider evidence;
- recipient/destination reference;
- whether delivery is proven, failed or unknown;
- whether external read evidence exists;
- whether a platform-native G8 visibility requirement is linked and its separately authoritative state;
- whether retry/reconciliation/fallback action is required.

It MUST be recomputable from immutable intents, attempts and provider evidence.

## Retry/reconciliation v1

G9 authorizes bounded retry of the same admitted WhatsApp channel.

Retry MUST:
- create a new attempt, never rewrite the prior one;
- use a bounded maximum attempt count;
- use deterministic backoff policy metadata;
- stop/reconcile when stronger provider evidence already proves delivery;
- preserve unknown as unknown when evidence is insufficient;
- surface `fallback_action_required` when the retry budget is exhausted or authoritative awareness is still required.

`fallback_action_required` is a projection/operational signal. It does not authorize a second transport channel, escalation policy, response workflow or approval state.

## Exact persistence authority

The future G9 migration may create only:

```text
notification.notification_intent
notification.notification_attempt
notification.notification_provider_evidence
notification.notification_projection
notification.notification_dispatch_outbox
notification.notification_callback_inbox
```

All six relations MUST use tenant RLS + FORCE RLS where tenant-owned rows are present.

Application/BFF code receives no direct table mutation privilege. Effects must pass guarded capabilities. Provider callback and worker authorities must be narrower than application read/write authority.

## Read/API/UI authority

G9 may expose protected:
- create intent for one Alert;
- list/detail notification intent;
- delivery attempts/evidence;
- normalized current delivery projection;
- retry/reconciliation state;
- callback operational diagnostics without leaking secrets/raw PII;
- composed G8 authoritative native visibility state by reference/read only.

The UI MUST explicitly distinguish `sent`, `provider accepted`, `delivered`, external read evidence and G8 authoritative visibility.

## Explicit non-authority

G9 does not authorize:
- Alert create/resolve/reopen or policy changes;
- responsibility/current-action mutation;
- ACK or unacknowledge;
- G8 visibility receipt fabrication;
- response/waiting business-state machine;
- approval/budget/quote workflow;
- SLA/escalation/routing policy;
- ITSM;
- Automation/AIOps;
- provider write-back to Monitoring;
- email/SMS/push/Teams/Slack transports;
- production activation.

## Required implementation governance

Future implementation PR:
- branch prefix: `impl/g9-notification-delivery`;
- required label: `jlmirror-slice:g9-notification-delivery`;
- claim: `implementation/g9-notification-delivery/IMPLEMENTATION_CLAIM.json`;
- exact SQL: `sql/notification/001_notification_delivery.sql`;
- runtime workflow: `.github/workflows/g9-notification-delivery-runtime.yml`.

## Required proof

Implementation MUST prove:
- intent idempotency/equivalence;
- recipient != responsible/current-action owner remains representable;
- provider message reference != platform identity;
- at-least-once dispatch does not duplicate logical attempt/effect;
- duplicate callbacks are deduped;
- out-of-order callbacks reconcile monotonically without inventing stronger evidence;
- `sent != delivered`;
- delivery unknown remains unknown;
- external read evidence does not fabricate G8 authoritative view;
- retries create new immutable attempts and respect bounded budget;
- cross-tenant access/effects fail closed;
- callback authenticity/replay checks;
- direct application writes blocked;
- RLS/FORCE RLS and privileged owner/ACL closure;
- protected HTTP/BFF/UI journey;
- restart/replay/reconciliation;
- hardened runtime/container proof.

## Gate laws

```text
G9_AUTHORIZED != G10_AUTHORIZED
SENT != DELIVERED
DELIVERED != VIEWED
EXTERNAL_READ != AUTHORITATIVE_NATIVE_VIEW
NOTIFICATION_RECIPIENT != RESPONSIBLE_PERSON
NOTIFICATION_STATE != ALERT_LIFECYCLE
PROVIDER_ID != PLATFORM_ID
UNKNOWN != FAILED
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
