# G10 ITSM Incident — implementation design

Authorization: `g10.itsm-incident@1`

## Golden path

```text
current tenant authority + admitted Alert
 -> create JLMirror Incident
 -> independent Incident lifecycle
 -> Incident assignment/comments
 -> durable provider-neutral sync outbox
 -> external ticket link evidence
 -> reconciliation
 -> protected API/BFF/UI
```

## Authority

G10 owns Incident state only. Alerting, G8 and G9 remain reference/read-only boundaries.
Application admission is supplied as a current authority snapshot.

The worker has a narrow provider-sync capability and never gains Incident lifecycle authority.
Provider state never directly mutates canonical Incident lifecycle.

## Identity

`incident_id` is generated independently of `alert_id` and provider ticket references.
Provider ticket IDs are evidence/linkage only.

## Lifecycle

Only:
- open -> in_progress
- open -> resolved
- in_progress -> resolved
- resolved -> closed

No reopen in v1.

## Assignment and comments

At most one current assignee. Reassignment closes the prior assignment and creates an immutable successor.
Comments are immutable actor-attributed facts.

## Persistence

Exactly six `itsm.*` relations are created. All tenant-owned relations use RLS + FORCE RLS.
Application and worker invokers receive no direct table mutation privileges.
