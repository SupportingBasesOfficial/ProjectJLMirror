# G28 — White-label Branding

**Record #84 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

JLMirror is deployed as a white-label platform — customers present it as their
own product, not a third-party tool. G28 enables operators to configure a
platform name, brand color, and logo URL that replace JLMirror defaults in
the shell UI.

---

## 2. Branding fields

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| `brand_name` | TEXT | max 80 chars | Replaces "JLMirror" in the header |
| `brand_color` | TEXT | `#[0-9a-fA-F]{6}` | CSS hex; applied to `--brand` CSS variable |
| `logo_url` | TEXT | max 2048 chars | Shown as `<img>` before the platform name |

All fields are optional and nullable — unset means platform defaults apply.

---

## 3. Schema

### `g1.tenant_branding`

| Column | Notes |
|--------|-------|
| tenant_id | PK, FK to tenants |
| brand_name | nullable text |
| brand_color | nullable hex with CHECK constraint |
| logo_url | nullable URL |
| updated_at | last write timestamp |

GRANT: `jlmirror_app` → SELECT, INSERT, UPDATE; `jlmirror_owner` → SELECT.
No RLS — table is accessed via the tenant-scoped connection, which inherits
tenant isolation from the connection setup.

---

## 4. API

```
GET /api/v1/platform/branding
    → { configured: bool, brand_name?, brand_color?, logo_url?, updated_at? }

PUT /api/v1/platform/branding
    body: { brand_name?, brand_color?, logo_url? }
    → upsert via ON CONFLICT (tenant_id) DO UPDATE
    → validates brand_color regex; validates lengths
```

---

## 5. Frontend

### `useBranding` hook

Fetches `GET /api/v1/platform/branding` when a tenant is bound, caches
5 minutes. Applies `document.documentElement.style.setProperty("--brand", brand_color)`
when a brand color is configured; removes the property otherwise, falling back
to the global CSS default.

### `BrandingCard` in `PlatformPage`

- Shows current brand_name, brand_color (swatch + hex), logo_url when configured
- Edit form: text input for name, color picker + hex input for color, URL input for logo
- Save via PUT mutation; invalidates branding query cache

### `Shell.tsx` header

When branding is configured:
- Logo shown as `<img>` (max height 24px) if logo_url is set
- brand_name text replaces "JLMirror" in the header
- CSS variable `--brand` is updated globally so all accent colors follow the tenant's brand

---

## 6. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/014_g28_branding.sql`
- [x] `api/routers/branding.py`
- [x] `api/main.py` — branding router registered
- [x] `frontend/src/hooks/useBranding.ts`
- [x] `frontend/src/pages/PlatformPage.tsx` — BrandingCard
- [x] `frontend/src/components/Shell.tsx` — branding applied to header
