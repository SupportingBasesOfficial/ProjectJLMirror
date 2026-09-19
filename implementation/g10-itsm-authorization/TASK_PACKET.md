# G10 ITSM — Task Packet

Authorization: `g10.itsm-incident@1`  
Canonical base: `main@a701498188867e9b6e5e98a74716f755bf673fc5`

## Objective

Implement one truthful Incident golden path:

```text
admitted Alert
 -> create JLMirror Incident
 -> independent Incident lifecycle
 -> Incident assignment/comments
 -> durable provider-neutral sync
 -> external ticket link evidence
 -> reconciliation
 -> protected UI
```

## Mandatory laws
- Alert ID != Incident ID.
- Alert state != Incident state.
- Incident assignee != G8 responsible/current-action owner.
- Provider ticket ID != Incident ID.
- Provider status != Incident status.
- Sync state != Incident lifecycle.
- G10 != G11.

## Required behavior
1. Exactly one JLMirror Incident object type in v1.
2. Lifecycle only `open | in_progress | resolved | closed` with exact authorized edges.
3. One originating Alert reference; no automatic Alert->Incident creation.
4. Create replay returns same Incident; divergent replay conflicts.
5. At most one current Incident assignee; immutable history.
6. Immutable bounded comments.
7. Provider-neutral adapter contract only; no named vendor.
8. Durable sync outbox with at-least-once-safe provider create/link.
9. Ambiguous provider outcome remains unknown/reconciliation-required.
10. External provider status cannot directly mutate Incident lifecycle.
11. Alert/G8/G9 are read/reference-only from G10.

## Persistence ceiling
Only the six relations in the authorization manifest may be created.

## Required adversarial proof
Prove:
- create replay/equivalence conflict;
- no duplicate external ticket on retry;
- Incident lifecycle remains independent when Alert resolves;
- Alert does not resolve when Incident resolves/closes;
- assignment concurrency/history;
- immutable comments/transitions;
- provider-link dedupe;
- provider status cannot mutate canonical lifecycle;
- unknown sync recovery/reconciliation;
- cross-tenant denial;
- direct write denial;
- RLS/FORCE RLS;
- privileged owner/function/default-ACL poisoning rejection;
- HTTP/BFF/UI tenant/permission enforcement;
- hardened runtime/container.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`
