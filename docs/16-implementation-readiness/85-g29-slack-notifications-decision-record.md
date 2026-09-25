# G29 — Slack/Teams Notifications

**Record #85 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

JLMirror's notification pipeline (G9/G22) dispatches alerts through typed
channel adapters selected by the `channel_class` column on
`notification.notification_intent`. G22 added `email_smtp@1` and pre-reserved
`slack@1` in the CHECK constraint. G29 activates `slack@1` by implementing
the Slack incoming-webhook adapter and routing it in the dispatch worker.

Teams webhooks use the same Incoming Webhook format; a Teams destination URL
works without any code change.

---

## 2. Design

### `providers/slack.py`

- `send_message(*, destination_ref, template_name, correlation_id, timeout)` —
  matches the WhatsApp/email adapter interface exactly; dispatch routing is a
  single `elif channel_class == "slack@1":` branch with no adapter-specific
  logic in the worker.
- `destination_ref` — full `https://hooks.slack.com/...` (or Teams equivalent)
  webhook URL stored in `notification.destination_config`.
- Payload: Block Kit JSON with a `section` block (mrkdwn text) and a `context`
  block with the correlation ID for tracing.
- Dev mode: if `SLACK_DEV_MODE=1` or `destination_ref` is not an `https://`
  URL, logs to stderr and returns a `dev-slack-*` ref. No HTTP call made.
- Transport error → `SlackError("transport:...")` — dispatch records `outcome=unknown`.
- Slack rejection (non-200 or non-"ok" body) → `SlackError("slack_rejected:...")` —
  dispatch records `outcome=failed`.

### Templates

| template_name | Emoji | Headline |
|--------------|-------|----------|
| alert_notification | :warning: | Alert requires attention |
| alert_critical | :rotating_light: | CRITICAL alert |
| alert_resolved | :white_check_mark: | Alert resolved |
| incident_notification | :fire: | Incident requires attention |
| maintenance_scheduled | :tools: | Maintenance window scheduled |

---

## 3. Worker routing

`workers/notification_dispatch.py` — updated dispatch branch:

```python
if channel_class == "email_smtp@1":
    res = send_email(...)
elif channel_class == "slack@1":
    res = send_slack(...)
else:
    res = send_whatsapp(...)
```

`SlackError` added to the except tuple alongside `WhatsAppError` and `EmailError`.

---

## 4. Schema

No new SQL migration. `slack@1` was pre-authorized in the CHECK constraint
on `notification.notification_intent.channel_class` during G22:

```sql
channel_class TEXT NOT NULL CHECK (channel_class IN (
    'whatsapp_business@1',
    'email_smtp@1',
    'slack@1'
))
```

`destination_ref` for a Slack channel is the full webhook URL, stored plaintext
in `notification.destination_config.destination_ref`.

---

## 5. Frontend

`NotificationChannelsPage.tsx` — no changes required. The channel selector
already included `slack@1` with label "Slack Webhook" and the correct
"Webhook URL" field label and `https://hooks.slack.com/...` placeholder.

---

## 6. Deliverables

- [x] Decision record (this document)
- [x] `providers/slack.py` — Slack incoming-webhook adapter
- [x] `workers/notification_dispatch.py` — `slack@1` routing branch + `SlackError` handling
- [x] No SQL migration (channel class pre-authorized in G22)
- [x] No frontend changes (UI already supported `slack@1`)
