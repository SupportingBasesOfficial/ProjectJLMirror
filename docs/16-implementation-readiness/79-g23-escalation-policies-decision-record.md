# G23 — Escalation Policies

**Record #79 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

G21 added snooze/suppress, allowing operators to silence alerts temporarily.
G23 adds the complementary escalation path: if an alert remains active beyond
a configurable time, the platform automatically fires ordered notification steps
until the alert is acknowledged or resolved.

Escalation is opt-in per alert. A policy is a named, ordered list of steps;
each step has a delay (minutes since prior step) and a delivery target
(channel_class + destination_ref). At runtime, `alert_escalation` tracks
which step is due and when it was last fired.

---

## 2. Schema

### `alerting.escalation_policy`

| Column | Notes |
|--------|-------|
| policy_id | PK `esc:<uuid>` |
| tenant_id | RLS enforced |
| name, description | human-readable |
| deleted_at | soft delete |

### `alerting.escalation_step`

| Column | Notes |
|--------|-------|
| step_id | PK |
| policy_id, tenant_id | FK + RLS |
| step_number | 1-based; UNIQUE (policy_id, step_number) |
| delay_minutes | relative to prior step (0 = fire immediately after arming for step 1) |
| channel_class | whatsapp_business@1 \| email_smtp@1 \| slack@1 |
| destination_ref | email / phone / URL |
| payload_ref | optional payload template reference |

### `alerting.alert_escalation`

Runtime state tracking; one row per escalating alert.

| Column | Notes |
|--------|-------|
| escalation_id | PK |
| alert_id, tenant_id | FK + UNIQUE (alert_id, tenant_id) |
| policy_id | FK to escalation_policy |
| current_step | starts at 1 |
| armed_at | when escalation started |
| last_fired_at | updated after each step fires |
| completed_at | set when all steps exhausted |

---

## 3. Functions

| Function | Caller | Purpose |
|----------|--------|---------|
| `g23_create_policy(tenant, name, description)` | app | Create policy |
| `g23_delete_policy(tenant, policy_id)` | app | Soft-delete policy |
| `g23_add_step(tenant, policy_id, step_number, delay_minutes, channel, dest, payload_ref)` | app | Append step |
| `g23_delete_step(tenant, policy_id, step_number)` | app | Remove step |
| `g23_arm_alert(tenant, alert_id, policy_id)` | app | Arm escalation for alert |
| `g23_disarm_alert(tenant, alert_id)` | app | Remove escalation state |
| `g23_advance_step(tenant, escalation_id, next_step)` | worker | Update current_step + last_fired_at after firing |

Invoker roles:
- `jlmirror_g23_esc_app_invoker` → granted to `jlmirror_app`
- `jlmirror_g23_esc_worker_invoker` → granted to `jlmirror_worker`

---

## 4. API

```
GET    /api/v1/escalation-policies
POST   /api/v1/escalation-policies          body: { name, description }
GET    /api/v1/escalation-policies/{id}
DELETE /api/v1/escalation-policies/{id}

POST   /api/v1/escalation-policies/{id}/steps/{step_number}
       body: { delay_minutes, channel_class, destination_ref, payload_ref? }
DELETE /api/v1/escalation-policies/{id}/steps/{step_number}

GET    /api/v1/alerts/{alert_id}/escalation-policy
POST   /api/v1/alerts/{alert_id}/escalation-policy   body: { policy_id }
DELETE /api/v1/alerts/{alert_id}/escalation-policy
```

---

## 5. Escalation worker

`workers/escalation.py` — runs on every worker tick.

Logic:
1. Query `alert_escalation` rows where
   `now() - COALESCE(last_fired_at, armed_at) >= step.delay_minutes`
2. For each due step: verify alert is not snoozed (G21 snooze check)
3. Insert `notification_intent` + `dispatch_outbox` entry for the step's
   channel/destination
4. Call `g23_advance_step` to record the firing and advance to next step
   (sets `completed_at` if no further steps remain)

Added to `workers/run_all.py` processor list as `("escalation", escalation)`.

---

## 6. Frontend

- `EscalationPage.tsx` — new page listing policies
  - Create policy button; click policy to see detail
  - `PolicyDetail`: ordered step list (step number circle, delay label, channel badge, destination)
  - `AddStepForm`: step_number (auto-incremented), delay_minutes, channel_class, destination_ref
- `Shell.tsx` — "Escalation" nav item added (visible to operators, gated on `monitoring:operate`)

---

## 7. Snooze interaction

G21 snooze takes priority over escalation. If an alert has an active snooze
at the moment the worker picks up a due escalation step, that step is skipped
(not fired, not advanced). The step becomes due again after the snooze expires.

This preserves the invariant that a snoozed alert generates no notifications.

---

## 8. Deliverables

- [x] Decision record (this document)
- [x] `sql/alerting/004_g23_escalation.sql`
- [x] `api/routers/escalation.py`
- [x] `api/main.py` — escalation router registered
- [x] `workers/escalation.py`
- [x] `workers/run_all.py` — escalation processor added
- [x] `frontend/src/pages/EscalationPage.tsx`
- [x] `frontend/src/components/Shell.tsx` — Escalation nav item
