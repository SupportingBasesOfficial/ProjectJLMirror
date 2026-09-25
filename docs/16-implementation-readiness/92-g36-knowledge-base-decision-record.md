# G36 — Knowledge Base

**Record #92 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-25**

---

## 1. Context

JLMirror operators accumulate institutional knowledge during incidents: runbooks,
root-cause analyses, workarounds, and configuration notes.  G36 provides a
tenant-scoped knowledge base where this knowledge can be authored, searched, and
linked to incidents — creating a durable connection between live operations and
accumulated institutional memory.

---

## 2. Architecture

No background worker is needed.  The knowledge base is synchronous: full-text search
runs via PostgreSQL `to_tsvector`/`plainto_tsquery` at query time, powered by a
GIN index.  Incident linking is a simple many-to-many join with no external side-effects.

---

## 3. Schema

### `g1.kb_category`
| Column | Notes |
|--------|-------|
| category_id | `'kbc:<uuid>'` |
| tenant_id | FK → g1.tenants |
| name, slug | UNIQUE (tenant_id, slug); slug auto-derived from name |
| parent_id | self-referential FK for sub-categories |

### `g1.kb_article`
| Column | Notes |
|--------|-------|
| article_id | `'kba:<uuid>'` |
| tenant_id | FK → g1.tenants |
| category_id | FK → kb_category (nullable) |
| title, body | TEXT; body is Markdown |
| status | `draft / published / archived` |
| tags | `TEXT[]` |
| created_by | principal_id at creation time |

GIN index: `to_tsvector('english', title || ' ' || body)` — enables
`plainto_tsquery` full-text search at query time.  Weighting (title > body) is
applied in the API query with `setweight`, independent of the index structure.

### `g1.kb_article_incident`
Many-to-many link between an article and an incident reference (incident_id is stored
as an opaque text reference; no FK into `itsm.incident` to remain agnostic of the
incident schema version).  `CASCADE DELETE` on `article_id` ensures links are removed
when the article is deleted.

---

## 4. API

Prefix: `/api/v1/kb`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/categories` | List all categories |
| POST | `/categories` | Create; slug auto-derived |
| DELETE | `/categories/{id}` | Hard delete |
| GET | `/articles` | List with optional `?q=` (FTS), `?category_id=`, `?status=` |
| GET | `/articles/{id}` | Full article + incident links |
| POST | `/articles` | Create (status defaults to draft) |
| PUT | `/articles/{id}` | Partial update (title, body, category, status, tags) |
| DELETE | `/articles/{id}` | Hard delete (cascades incident links) |
| POST | `/articles/{id}/incidents` | Link incident |
| DELETE | `/articles/{id}/incidents/{inc_id}` | Unlink incident |

All endpoints require a valid tenant session.  No domain-specific permission beyond
tenant membership (knowledge base is read/write for any authenticated principal).

---

## 5. Frontend

`frontend/src/pages/KnowledgeBasePage.tsx` — single-page layout:

- **Article list** — search bar (350 ms debounce → full-text query), status filter,
  category filter; each card shows title, status badge, category, tags, date.
- **Article detail** — title, status, category, tags, Markdown body (monospace render),
  incident link panel (list + link/unlink form).
- **Article editor modal** — title, category select, status select, body textarea
  (monospace), tags input; used for both create and edit.
- **Category creation** — inline form shown/hidden via "+ Category" toggle.

Shell nav item "Knowledge Base" shown to all authenticated principals (no
`monitoring:operate` gate — KB is visible to all tenant members).

---

## 6. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/021_g36_knowledge_base.sql` — kb_category, kb_article, kb_article_incident
- [x] `api/routers/kb.py` — categories, articles, FTS, incident linking
- [x] `api/main.py` — kb router registered
- [x] `frontend/src/pages/KnowledgeBasePage.tsx` — article list, detail, editor, incident links
- [x] `frontend/src/components/Shell.tsx` — Knowledge Base nav item + render

---

## 7. Completion note

G36 is the final implementation gate (G29–G36).  JLMirror is now feature-complete
for the initial commercial release:

| Gate | Feature | Status |
|------|---------|--------|
| G29 | Slack/Teams Notifications | ✅ |
| G30 | ITSM Change Management | ✅ |
| G31 | SLA Management | ✅ |
| G32 | Automation Runtime | ✅ |
| G33 | Scheduled Reports | ✅ |
| G34 | Prometheus/Alertmanager Source | ✅ |
| G35 | Infrastructure Governance | ✅ |
| G36 | Knowledge Base | ✅ |
