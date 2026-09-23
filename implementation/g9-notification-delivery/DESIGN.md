# G9 Notification + Delivery — implementation design

Authorization: `g9.notification-delivery@1`

## Golden path

```text
current tenant authority + active Alert
 -> immutable notification intent
 -> durable dispatch outbox
 -> one immutable WhatsApp attempt
 -> provider evidence/callback inbox
 -> recomputed normalized delivery projection
 -> protected API/BFF/UI
```

## Authority

Application admission remains outside G9 and is supplied as a bounded current-authority snapshot.
G9 never derives authorization from notification responsibility, provider IDs or destination data.

The worker has a separate narrow dispatch capability. Provider callbacks enter only after adapter
authenticity/replay/routing checks and are persisted through a callback-specific capability.

## Identity

Platform IDs are generated independently from provider message/callback references.
A provider reference is evidence, never notification identity.

## Delivery semantics

`sent`, `provider_accepted`, `delivered`, `external_read_observed`, `failed` and
`unknown` remain evidence-derived states. External read evidence never creates a G8 native
visibility receipt.

## Retry

Retry means a new immutable attempt for the same intent and same `whatsapp_business@1` channel.
The outbox is the durable responsibility. A bounded retry budget is carried by the intent/projection.
Exhaustion yields `fallback_action_required`; it does not authorize another channel.

## Persistence

Exactly six G9 relations are created. Tenant RLS + FORCE RLS is mandatory.
Application, worker and callback invokers have no direct table mutation privilege.
