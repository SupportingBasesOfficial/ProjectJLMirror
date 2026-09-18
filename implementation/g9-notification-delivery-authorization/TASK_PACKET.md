# G9 Notification + Delivery — Task Packet

Authorization: `g9.notification-delivery@1`  
Canonical base: `main@a264e17852bfd114546438ee9094c7655c920839`

## Objective

Implement one truthful WhatsApp notification golden path:

```text
Alert/context
 -> immutable notification intent
 -> durable dispatch
 -> WhatsApp attempt
 -> normalized provider evidence
 -> current delivery projection
 -> protected UI
 -> retry/reconciliation/fallback-required signal
```

## Mandatory laws

- Sent != delivered.
- Provider accepted != delivered.
- Delivered != viewed.
- External read != G8 authoritative native view.
- Notification recipient != responsible person.
- Notification recipient != current action owner.
- Provider ID != platform ID.
- Unknown != failed.
- G9 != G10.

## Required behavior

1. Admit only `whatsapp_business@1`.
2. Create immutable tenant-owned intent bound to one Alert and protected destination reference.
3. Dispatch through durable outbox with at-least-once-safe logical identity.
4. Record immutable attempt history; retry creates a new attempt.
5. Normalize provider acceptance/delivery/read/failure/unknown evidence without provider IDs becoming platform identity.
6. Deduplicate callbacks durably and reject unauthenticated/replayed/unbindable callbacks.
7. Reconcile out-of-order evidence monotonically without inventing stronger evidence.
8. Preserve delivery unknown when the channel cannot prove more.
9. Treat external read evidence as supplementary; when authoritative awareness is required, compose/read the G8 native requirement/receipt instead of fabricating it.
10. Surface bounded retry/reconciliation/fallback-required state.
11. Keep Alert lifecycle, ACK, responsibility, response, approval and ITSM outside G9.

## Persistence ceiling

Only the six relations in the authorization manifest may be created.

## Required adversarial proof

Prove:
- intent replay/equivalence conflict;
- duplicate/redelivered outbox processing;
- attempt concurrency and retry budget;
- duplicate callbacks;
- callback authenticity/replay window;
- out-of-order accepted/delivered/read evidence;
- sent-vs-delivered distinction;
- external-read-vs-native-view distinction;
- cross-tenant denial;
- direct write denial;
- RLS/FORCE RLS;
- privileged owner/function/default-ACL poisoning rejection;
- HTTP/BFF/UI tenant/permission enforcement;
- restart/replay/reconciliation;
- hardened runtime/container.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`
