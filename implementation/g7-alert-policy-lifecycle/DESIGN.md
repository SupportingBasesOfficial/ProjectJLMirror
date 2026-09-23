# G7 Alert Policy + Lifecycle — implementation design

Authorization: `g7.alert-policy-lifecycle@1`

## Exact product path

```text
accepted G6 resync
 -> reread current Monitoring owner state
 -> evaluate one immutable policy version
 -> create or resolve one Alert occurrence
 -> read bounded list/detail
 -> render protected list/detail UI
```

## Policy version law

A policy identity owns immutable numbered versions. New Alert creation requires the
version to be the tenant policy's current effective enabled version.

An Alert that was created by version V remains pinned to V. If V is later
superseded or disabled, V gains no new-occurrence authority. A superseded
version cannot later be selected as effective again. The only later
effect V may produce is the terminal resolution of an Alert occurrence that V
already created, after a fresh current Monitoring reread proves the V condition
no longer matches. This continuation rule never reopens an Alert and never
creates a new Alert from a non-effective version.

## Occurrence identity

Problem-source occurrence identity is the canonical `problem_id`. Monitoring
already makes a resolved Problem terminal under that identity.

Health-source occurrence identity begins at the current projection revision that
first changes a non-active policy/resource pair into a matching pair. While the
Alert is active, later revisions belong to that same Alert occurrence. After it
resolves, a later matching projection revision creates a new `alert_id`.

The database enforces at most one active Alert for the same
`tenant + policy_id + source_kind + source_subject_id` across policy versions.
A newer effective version therefore cannot create a second active Alert over an
occurrence still owned by an older version. The older pinned version may only
continue that already-open occurrence to terminal resolution.

Every create/resolve decision is separately idempotent by exact source
projection revision and immutable policy content hash. Replaying the same
effectful source revision returns the already-recorded effect and Alert identity.

## Currentness

No event body is policy truth. Evaluation rereads:
- current Monitoring source generation and source evidence;
- the current canonical Problem or Health projection;
- projection evidence state and revision.

A generation mismatch, missing owner state, non-current source evidence or
non-current projection evidence fails closed and produces no lifecycle effect.

## Condition families

Problem v1:
- source state must be `active`;
- minimum severity is one of
  `unknown | informational | warning | degraded | critical`;
- optional exact Monitoring source/resource selectors.

Health v1:
- matching classes are a non-empty subset of
  `unknown | healthy | degraded | unhealthy`;
- optional exact Monitoring source/resource selectors.

No executable expression surface exists.

## Persistence authority

Application code receives no table mutation privilege. Effectful calls are
guarded database functions owned by the G7 executor role. Read calls are also
bounded functions. All six G7 relations use tenant RLS with FORCE RLS.
