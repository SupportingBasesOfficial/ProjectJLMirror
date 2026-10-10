# G22 — Email Notifications

**Record #78 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

G9 established the notification delivery pipeline against a single channel:
`whatsapp_business@1`. G22 extends the pipeline to support multiple delivery
channels in parallel — beginning with SMTP email (`email_smtp@1`) — without
changing the durable outbox architecture or the notification intent model.

The channel_class field was already present on `notification_intent` but
gated by a CHECK constraint that allowed only WhatsApp. G22 relaxes that
constraint and adds full routing logic in the dispatch worker.

---

## 2. Channel model

All channels implement the same adapter interface:

```python
send_message(
    *, destination_ref: str, template_name: str,
    correlation_id: str, timeout: float = 10.0
) -> {"provider_message_ref": str, "accepted": bool, "raw": {...}}
```

`destination_ref` meaning by channel:

| channel_class | destination_ref |
|---------------|-----------------|
| `whatsapp_business@1` | phone / msisdn ref |
| `email_smtp@1` | email address |
| `slack@1` | webhook URL (reserved for G29) |

Dev mode: if SMTP_HOST is not set, emails are written to the application log
(no-op). The WhatsApp adapter already had an equivalent mechanism.

---

## 3. Schema changes

### `notification.notification_intent` — constraint widened

```sql
CHECK (channel_class IN ('whatsapp_business@1', 'email_smtp@1', 'slack@1'))
```

The `slack@1` value is reserved for G29 — its adapter does not exist yet,
but reserving the enum value now avoids a second constraint migration.

### `notification.notification_destination_config` — new table

Stores named delivery endpoints per tenant. Operators add email addresses
(or WhatsApp refs) through the Channels UI; those destinations are then
specified as `destination_ref` when creating a notification intent.

| Column | Notes |
|--------|-------|
| destination_config_id | PK `dst:<uuid>` |
| tenant_id | RLS enforced |
| channel_class | whatsapp_business@1 \| email_smtp@1 \| slack@1 |
| destination_ref | email / phone / URL |
| label | human-readable name |
| created_at | immutable |
| deleted_at | soft delete |

---

## 4. Functions

| Function | Caller | Purpose |
|----------|--------|---------|
| `g22_add_destination(tenant, channel, ref, label)` | app role | Insert destination config |
| `g22_delete_destination(tenant, dest_id)` | app role | Soft-delete destination |

Invoker role: `jlmirror_g22_dest_app_invoker` → granted to `jlmirror_app`.

---

## 5. API

```
GET    /api/v1/alerting/notification-channels
       → list destinations for tenant

POST   /api/v1/alerting/notification-channels
       body: { channel_class, destination_ref, label }
       → create destination

DELETE /api/v1/alerting/notification-channels/{dest_id}
       → soft-delete destination
```

`POST /api/v1/alerting/alerts/{alert_id}/notifications` now accepts an
optional `channel_class` field (default `whatsapp_business@1`).

---

## 6. Dispatch worker changes

`workers/notification_dispatch.py` fetches `ni.channel_class` from the
notification_intent JOIN and routes:
- `email_smtp@1` → `providers.email.send_message()`
- `whatsapp_business@1` (default) → `providers.whatsapp.send_message()`

Both adapters raise typed exceptions (`EmailError`, `WhatsAppError`) with
a `transport:` prefix for network errors and bare class names for SMTP/API
errors. The worker maps both to `outcome = "unknown"` (for transport) or
`"failed"` (for provider rejection), consistent with the existing G9 retry
policy (max 3 attempts, 30 s back-off).

---

## 7. Frontend

- `NotificationChannelsPage.tsx` — new page showing the destination roster
  - Add form: channel selector, destination ref input, label input
  - Table: channel badge, label, address, added date, remove button
  - Gated on `monitoring:operate` permission (same as Maintenance)
- `Shell.tsx` — "Channels" nav item added (visible to operators)

---

## 8. Environment variables (email adapter)

| Variable | Default | Notes |
|----------|---------|-------|
| `SMTP_HOST` | *(unset)* | If unset, dev-mode log-only |
| `SMTP_PORT` | 587 | |
| `SMTP_USER` | | Auth username (optional) |
| `SMTP_PASSWORD` | | Auth password |
| `SMTP_FROM` | SMTP_USER or noreply@jlmirror.com | From: address |
| `SMTP_TLS` | starttls | starttls \| ssl \| none |

---

## 9. Deliverables

- [x] Decision record (this document)
- [x] `sql/z_integration/012_g22_email_notification.sql`
- [x] `providers/email.py` — SMTP adapter
- [x] `api/routers/notifications.py` — channel_class in IntentCreate, destination endpoints
- [x] `workers/notification_dispatch.py` — routing by channel_class
- [x] `frontend/src/pages/NotificationChannelsPage.tsx`
- [x] `frontend/src/components/Shell.tsx` — Channels nav item
