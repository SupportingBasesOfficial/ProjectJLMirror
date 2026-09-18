# G8 Human Operations — implementation design

Authorization: `g8.human-operations@1`

## Product path

```text
current authenticated/authorized tenant actor
 -> reread canonical Resource or active Alert
 -> record responsibility/action/ACK/native visibility fact
 -> derive current action + visibility state
 -> expose protected API/BFF/UI + immutable timeline
```

## Authority law

Human-operations facts never grant authorization.

Every effect requires:
1. a caller-side current G1 admission/authorization decision;
2. a bounded immutable authority snapshot passed to the persistence capability;
3. tenant/principal equivalence between the admitted actor and the requested effect;
4. a fresh database reread of the owning Monitoring Resource or G7 Alert.

The database snapshot is evidence of the already-admitted current authority, not a
replacement IAM. Unknown/missing/non-current authority fails closed.

## Responsibility

Resource responsibility supports multiple concurrent principals. Identity/content
is immutable. Ending an assignment is a terminal closure carrying ending actor,
time and reason. A closed assignment is never reopened.

## Current action

Exactly one current action assignment may exist per Alert. Reassignment atomically
closes the prior assignment and creates the successor. The current-action
projection is maintained only by guarded G8 capabilities and can be rebuilt from
assignment history plus the current G7 Alert.

`no_human_action_required` is projection-only and never creates an owner.

## ACK

ACK is append-only actor/time/scope evidence. It never updates G7 Alert lifecycle,
responsibility, current-action ownership or visibility.

## Native visibility

Only `platform_native_authenticated_view@1` is admitted. Creating a requirement
requires a current active Alert. Recording its receipt requires the exact required
viewer and current platform authority. A receipt may arrive after Alert resolution
only for a requirement created while the Alert was active; it remains late evidence
and cannot mutate Alert/action state.

## Timeline

Timeline is a read projection over authoritative assignment start/end, ACK,
visibility requirement and visibility receipt facts. Projection changes are not
timeline authority.

## Persistence authority

Application code has no direct table mutation privilege. All effects enter through
bounded SECURITY DEFINER capabilities owned by a dedicated NOLOGIN executor.
All six G8 relations use tenant RLS + FORCE RLS.
