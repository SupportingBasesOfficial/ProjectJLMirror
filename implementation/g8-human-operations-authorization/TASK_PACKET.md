# G8 Human Operations — Task Packet

Authorization: `g8.human-operations@1`  
Canonical base: `main@be9d2a2fe49c308d4d8c9ca06e9ebafbb4ae69f8`

## Objective

Implement one truthful human-operations golden path over canonical Resources and Alerts:

```text
resource responsibility
+ alert current-action assignment
+ actor-attributed ACK
+ authoritative native visibility
-> protected read/write surfaces
-> derived timeline/UI
```

## Mandatory laws

- Alert lifecycle != responsibility.
- Responsibility != current action owner.
- Current action owner != acknowledger.
- Viewer != acknowledger.
- ACK != Alert lifecycle.
- Responsibility != authorization.
- Native visibility != external delivery.
- No external receipt != not viewed.
- Timeline != source of truth.
- G8 != G9.

## Required behavior

1. Support multiple concurrent responsible principals for one canonical Monitoring Resource.
2. Preserve effective intervals and assigning/ending actor/source with one-way terminal closure.
3. Support exactly one current Alert action owner while retaining history; `no_human_action_required` is projection-only and never creates a fake owner.
4. Record ACK as immutable actor/time/scope evidence; no unack.
5. Require current authorization and active/current Alert before new ACK/action effects.
6. Provide JLMirror-native authenticated visibility requirements for internal or customer principals only while an Alert is active/current.
7. Derive `not_viewed_yet` only for the admitted native visibility path while no authoritative receipt exists.
8. Record immutable native visibility receipt and derive `viewed`; a receipt for a pre-existing requirement may arrive after Alert resolution only as late evidence and must not mutate Alert/action state.
9. Never infer WhatsApp/email/provider delivery or external read status.
10. Expose bounded protected API/BFF/UI and derived timeline.

## Persistence ceiling

Only the six relations enumerated by the authorization manifest may be created.

Direct application table mutation is forbidden.

## Required adversarial proof

Prove:
- cross-tenant denial;
- stale/resolved Alert denial for new human effects;
- assignment concurrency, terminal closure and exactly one current action owner;
- ACK replay/equivalence conflict;
- viewer != acknowledger;
- multiple responsible principals;
- native visibility transition;
- absence of fabricated external delivery/read state;
- RLS/FORCE RLS;
- direct-write denial;
- privileged function ACL/owner/default-privilege poisoning rejection;
- HTTP/BFF/UI tenant and permission enforcement;
- restart/replay/reconciliation and hardened runtime container.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`
