# JLMirror Human Operations Model

Status: canonical project-memory source
Authority seed: Issue #149

This document defines the required conceptual separation for future human-operations authorization/runtime. It is not by itself implementation authority.

## Core rule
Never collapse responsibility, acknowledgement, notification, delivery, viewing, response, approval and resolution into one giant status.

## Orthogonal dimensions
1. **Resource responsibility** — one or more principals responsible for a device/resource/operation.
2. **Current action owner** — who must act now.
3. **Acknowledgement** — who acknowledged, when, under which authority/scope.
4. **Notification intent** — who/destination should be contacted and why.
5. **Delivery attempt/state** — requested, sent, provider-accepted, delivered, failed or unknown according to admitted channel evidence.
6. **View/read evidence** — whether viewing is authoritatively proven, by whom, when; last viewer and immutable receipt history where supported.
7. **Response/waiting state** — e.g. already notified awaiting response, awaiting technical position, awaiting customer action.
8. **Approval workflow** — e.g. quote/budget sent, approval requested, approved, rejected, expired/cancelled.
9. **Next-action projection** — required next step, owner, deadline/SLA and reason.
10. **Escalation** — durable policy/timer-driven transfer/expansion of action responsibility.

## Internal and customer-side authority
The system must be able to establish technical authority for awareness/visibility on both sides when the process requires it:
- internal operator/NOC/technician/responsible principal;
- customer-side responsible person, service owner or approver.

A critical workflow must not accept indefinite `view_status_unknown` as its planned end state when proof of awareness is required.

## Channel admission rule
Every communication channel/integration must declare capabilities such as:
- dispatch evidence;
- provider acceptance evidence;
- delivery evidence;
- read/view evidence;
- authenticated actor identity;
- response/action evidence.

If an external channel cannot prove read/view strongly enough for the workflow, it may still be used as transport, but the required action must terminate on a JLMirror-controlled authenticated surface (for example a secure portal/link/action) that can create authoritative view/response evidence.

## Example E2E
`equipment critical`
-> `João and Maria are responsible`
-> `João ACKs`
-> `customer notified via WhatsApp`
-> `delivery proven`
-> `nobody has viewed yet` (only if technically provable)
-> `budget/quote sent`
-> `awaiting approval`
-> **continue tracking and presenting whether/when the customer has viewed the item**
-> `Maria remains responsible`
-> `next action belongs to customer`
-> `waiting SLA continues`
-> `customer views/authenticates`
-> `view receipt recorded`
-> `customer approves/rejects/responds`
-> `next action recomputed`

The transition to another business phase never erases delivery/view evidence.

## Required audit facts
Future runtime must be capable of reconstructing:
- responsible principals assigned/removed/delegated;
- assignment source/actor/effective interval;
- ACK actor/time/scope/authority;
- notification recipient, destination, channel and reason;
- every delivery attempt and provider evidence;
- authoritative delivery/read/view receipts;
- all viewers, last viewer and last viewed time where supported;
- response receipt;
- quote/budget sent and version/reference;
- approval request/decision/actor/time;
- current action owner changes;
- SLA/waiting-clock changes;
- escalation;
- lifecycle resolution/closure in owning domains.

## Identity laws
- `NOTIFICATION RECIPIENT != RESPONSIBLE PERSON`
- `RESPONSIBLE PERSON != CURRENT ACTION OWNER`
- `VIEWER != ACKNOWLEDGER`
- `ACKNOWLEDGEMENT != RESOLUTION`
- `SENT != DELIVERED`
- `DELIVERED != VIEWED`
- `VIEWED != RESPONDED`
- `APPROVAL != DELIVERY`
- `PROVIDER ACK != JLMIRROR ACK`

## Timeline rule
A unified operational timeline is a projection over immutable authoritative facts. It may compose events from Alerting, responsibility, notification, approval and ITSM, but it must never become a second writable business source of truth.
