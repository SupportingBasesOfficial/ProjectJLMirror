# G10 ITSM — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@a701498188867e9b6e5e98a74716f755bf673fc5`  
**Authorization ID:** `g10.itsm-incident@1`

## Purpose

Authorize only the tenth product increment: create/link one JLMirror-owned Incident from an admitted Alert, expose its own lifecycle/assignment/comments, and synchronize it through a provider-neutral ITSM adapter without collapsing Alert and Incident identity or lifecycle.

## Golden path

```text
admitted current Alert
 -> immutable incident creation/link command
 -> JLMirror Incident identity
 -> Incident lifecycle + assignment + comments
 -> durable provider sync outbox
 -> provider-neutral ITSM adapter
 -> external ticket reference/evidence
 -> reconciliation
 -> protected API/BFF/UI
```

## Core identity laws

```text
ALERT_ID != INCIDENT_ID
ALERT_STATE != INCIDENT_STATE
INCIDENT_OWNER != ALERT_CURRENT_ACTION_OWNER
INCIDENT_ASSIGNEE != RESPONSIBLE_PERSON
PROVIDER_TICKET_ID != INCIDENT_ID
PROVIDER_STATUS != INCIDENT_STATUS
INCIDENT_COMMENT != ALERT_NOTE
INCIDENT_RESOLVED != ALERT_RESOLVED
ALERT_RESOLVED != INCIDENT_RESOLVED
ITSM_SYNC_STATE != INCIDENT_LIFECYCLE
TIMELINE != MUTABLE_BUSINESS_TRUTH
```

## Incident v1 lifecycle

The only admitted canonical lifecycle is:

```text
open -> in_progress -> resolved -> closed
```

Rules:
- `open -> in_progress` is optional; `open -> resolved` is allowed;
- `in_progress -> resolved` is allowed;
- `resolved -> closed` is allowed;
- `resolved -> in_progress` and `closed -> *` are NOT authorized in v1;
- Alert lifecycle never drives these transitions implicitly;
- Incident transitions require current ITSM authority and immutable transition facts.

## Alert linkage

- one Incident v1 MUST pin one originating Alert;
- creating an Incident requires a current admitted Alert, but does not mutate the Alert;
- retries/replays of the same logical create action MUST return the same Incident;
- a later Alert resolution does not resolve/close the Incident;
- Incident lifecycle changes do not resolve/reopen the Alert.

## Assignment v1

Incident assignment is ITSM-owned and separate from G8 responsibility/current-action.

- at most one current Incident assignee;
- assignee is a stable platform principal;
- reassignment atomically closes prior assignment and creates a successor;
- assignment history is immutable;
- assignment grants no authorization by itself.

## Comments v1

Comments are immutable actor-attributed ITSM facts:
- opaque comment ID;
- tenant + Incident;
- actor principal;
- bounded body;
- actor/time/current authority evidence;
- idempotent logical action/equivalence.
No edit/delete in v1.

## Provider-neutral adapter

No external ITSM vendor is selected by this authorization.

The implementation MUST expose one provider-neutral adapter contract and may use a fixture/reference adapter for proof. Future ServiceNow/Jira/etc. adapters require separate admission/configuration but MUST conform to this contract.

Provider sync is evidence, not business authority:
- external ticket/reference ID never becomes JLMirror Incident identity;
- external provider status never mutates Incident lifecycle without an explicit separately-authorized mapping/action;
- provider create/link retry must not duplicate the external logical ticket;
- ambiguous provider outcome remains `unknown` and enters reconciliation.

## Sync states

Provider synchronization uses:

```text
pending
dispatching
linked
failed
unknown
reconciliation_required
```

These are integration states only.

## Exact persistence authority

The future G10 migration may create only:

```text
itsm.incident
itsm.incident_transition
itsm.incident_assignment
itsm.incident_comment
itsm.incident_provider_link
itsm.incident_sync_outbox
```

All six relations MUST use tenant RLS + FORCE RLS.

Application/BFF code receives no direct mutation privilege. Worker/provider adapter authority must be narrower than application authority.

## Read/API/UI authority

G10 may expose protected:
- create Incident from one Alert;
- list/detail Incident;
- transition Incident lifecycle;
- assign/reassign Incident;
- add/list comments;
- provider sync/link/reconciliation state;
- read-only referenced Alert summary;
- derived timeline over Incident immutable facts.

## Explicit non-authority

G10 does not authorize:
- Alert lifecycle/policy mutation;
- G8 responsibility/current-action/ACK mutation;
- G9 notification/delivery mutation;
- automatic Alert->Incident creation;
- Incident reopening after resolved/closed;
- SLA timers/escalation;
- service catalog;
- change/RFC;
- approval/budget/quote;
- tasks/subtasks;
- maintenance;
- knowledge base;
- Automation/AIOps;
- named external ITSM vendor integration;
- production activation.

## Required implementation governance

Future implementation PR:
- branch prefix: `impl/g10-itsm`;
- required label: `jlmirror-slice:g10-itsm`;
- claim: `implementation/g10-itsm/IMPLEMENTATION_CLAIM.json`;
- exact SQL: `sql/itsm/001_incident.sql`;
- runtime workflow: `.github/workflows/g10-itsm-runtime.yml`;
- workflow name: `JLMIRROR G10 ITSM Runtime`;
- entrypoint: `python tools/g10/run_itsm_runtime.py`.

## Required proof

Implementation MUST prove:
- Alert ID and Incident ID remain different;
- Incident create replay/equivalence conflict;
- no automatic Incident creation;
- Incident lifecycle independent from Alert lifecycle;
- assignment independent from G8 ownership/responsibility;
- immutable comments and transitions;
- one current assignee with concurrency proof;
- provider create/link is idempotent and provider ID != Incident ID;
- unknown provider outcome enters reconciliation;
- provider status cannot directly mutate Incident lifecycle;
- cross-tenant effects fail closed;
- direct app/worker table writes blocked;
- RLS/FORCE RLS and privileged owner/ACL closure;
- protected HTTP/BFF/UI journey;
- restart/replay/reconciliation;
- hardened runtime/container proof.

## Gate laws

```text
G10_AUTHORIZED != G11_AUTHORIZED
ALERT_ID != INCIDENT_ID
ALERT_STATE != INCIDENT_STATE
PROVIDER_TICKET_ID != INCIDENT_ID
PROVIDER_STATUS != INCIDENT_STATUS
INCIDENT_ASSIGNEE != RESPONSIBLE_PERSON
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
