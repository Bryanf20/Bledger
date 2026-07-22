# Bledger Developer Guide

Django 6.0 + React (Vite) business management / POS system for Cameroonian SMEs. Standalone-first: SQLite, fully offline. Phase 2 adds cloud sync via an outbox pattern.

Design references: `Bledger_Design_v0.5.docx`, `Bledger_Feasibility_Design_v0.3.docx`, and `Bledger_UI_Design_Reference.docx` (the screen-level implementation baseline).

---

## 1. Getting started

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp ../.env.example ../.env
export DJANGO_SETTINGS_MODULE=bledger.settings.development
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server, proxies /api/* to :8000
npm run lint       # oxlint
npm run build
```

### Tests

```bash
cd backend
DJANGO_SETTINGS_MODULE=bledger.settings.testing pytest
```

Receipt/report PDF endpoints need WeasyPrint's system libraries (Pango, Cairo, GDK-PixBuf). If absent, those endpoints return 503 with a clear message — the rest of the app is unaffected.

### Settings modules

`bledger/settings/` — `base` (shared), `development` (SQLite + CORS for Vite), `standalone` (Phase 1 production: SQLite, `SYNC_ENABLED=False`), `connected` (Phase 2: PostgreSQL, sync on), `production` (inherits connected + hardening), `testing` (in-memory SQLite, fast hasher).

---

## 2. Locked architectural decisions

Do not revisit these without a design-doc change:

- **Django 6.0, DRF, TokenAuthentication** (`Authorization: Token <key>` — not Bearer). Session auth kept alongside for `/admin/`.
- **`BledgerUser`** extends `AbstractBaseUser`; role field `owner | manager | cashier`; cashiers authenticate by 4-digit PIN only (`pin_hash`, hashed like a password, independent of `password`).
- **Money is XAF as `PositiveIntegerField` everywhere. Never `Decimal`.** Formatting/rounding lives only in `apps/core/utils/xaf.py`.
- **`request.branch_id`** is stamped on every request by `DeploymentContextMiddleware` from `settings.BRANCH_ID`. Views never read settings directly for this.
- **`BaseModel`** (`apps/core/models.py`) for every synced table: UUID pk, `branch_id`, `created_at/updated_at`, soft delete (`deleted_at` + `SoftDeleteManager`), `synced_at`, `version` (auto-incremented in `save()`). Exceptions, by design: `Branch`, `BledgerUser`, `OutboxEntry`, `ProductTemplate`.
- **Outbox pattern** for Phase 2 sync: writes append an `OutboxEntry` inside the same transaction via `apps.sync.utils.write_outbox_entry()`.
- **Printing** is dict-in/bytes-out: `apps.printing.interface.print_receipt(sale_data)` is the only entry point; backend chosen by `settings.PRINTER_BACKEND` (`pdf` now, `thermal` stub for Phase 3). `apps.printing` never imports other apps' models — callers build the dict (`apps/sales/receipt_data.py`).
- **`django.tasks`** is the planned Phase 2 sync backend.

---

## 3. Backend layout

All apps under `backend/apps/`, mounted in `bledger/urls.py` under `/api/v1/`.

| App | Owns | Key endpoints |
|---|---|---|
| `core` | `BaseModel`, permissions, pagination, middleware, XAF helpers, health check | `GET /health/` |
| `auth_users` | `Branch`, `BledgerUser`, setup wizard | `POST /auth/login/`, `/auth/pin-login/`, `/auth/logout/`, `GET /auth/me/`; `GET /setup/status/`, `GET /setup/templates/`, `POST /setup/`, `POST /setup/load-template/`; `POST /users/` (owner) |
| `inventory` | `Category`, `Product`, `BranchPriceOverride`, `StockAdjustment`, `ProductTemplate` + fixtures | `/products/`, `/categories/`, `/price-overrides/` (upsert-on-create), `/stock-adjustments/` (append-only) |
| `sales` | `Sale`, `SaleLineItem`, `HeldSale`, receipt context | `/sales/` (+ `?date_from&date_to&payment_method&status&search`), `POST /sales/{id}/void/`, `GET /sales/{id}/receipt/` (PDF), `/held-sales/` (+ `POST {id}/restore/`) |
| `printing` | Printer abstraction, receipt.html (80mm), PDF backend | (no routes — called by sales/dashboard) |
| `suppliers` | `Supplier`, `Purchase`, `PurchaseLineItem`, `PurchasePayment` | `/suppliers/`, `/purchases/`, `POST /purchases/{id}/record-payment/` |
| `dashboard` | Aggregate views + CSV/PDF reports | `/dashboard/summary/`, `/top-products/`, `/payment-breakdown/`, `/sales-chart/`, `/stock-alerts/`; `/reports/{sales,products,stock}/` |
| `sync` | `OutboxEntry`, `write_outbox_entry()` | none yet (engine is Phase 2; routes commented out in root urls) |

### Permission model

`apps/core/permissions.py`: `IsOwner`, `IsManagerOrOwner`, `IsCashierOrAbove` — rank-based (`owner > manager > cashier`), deny-by-default if `role` is absent. Conventions:

- Inventory: read = cashier+, write = manager+.
- Sales: cashier+ but cashiers only see their own sales/held sales; `void` is manager+.
- Suppliers: entire app manager+ (unit costs are financial data cashiers never see).
- Dashboard: manager+ except `stock-alerts` (cashier+, explicitly per design doc E.5).

### Cross-cutting write conventions

- **Stock never moves via direct field edits.** Only `StockAdjustmentSerializer.create()`, `SaleSerializer.create()` (decrement), `VoidSaleSerializer.save()` (restore), and `PurchaseSerializer.create()` (increment) touch `Product.stock_level` — always `select_for_update()` inside `transaction.atomic()`, with an outbox write in the same transaction.
- **Financial records are immutable.** Sales and purchases have no PATCH/DELETE; corrections happen through purpose-built actions (`/void/`, `/record-payment/`) that append audit records.
- **Totals are server-computed.** `Sale.subtotal/total_amount`, `Purchase.total_amount/payment_status` are never client-supplied.
- **Branch scoping.** Every viewset filters by `request.branch_id` via a `BranchScopedQuerysetMixin`; `ProductViewSet` additionally unions in the HQ catalogue (`branch_id="HQ"`) — the Phase 2 multi-branch seam.
- **Soft delete** via `BaseModel.soft_delete()`; `HeldSale.restore` hard-deletes deliberately (transient data). Products deactivate (`is_active=False`) instead of any delete.
- **Every `DefaultRouter` sets `include_format_suffixes = False`** — a second router registering format suffixes raises under Django 6's stricter `register_converter()`.

---

## 4. Frontend layout

`frontend/` — React 19, Vite, React Query (`@tanstack/react-query`), Zustand (cart), React Hook Form, Tailwind 4, oxlint.

```
src/
  api/         axios client + one module per backend app
  hooks/       React Query wrappers (useProducts, useSuppliers, ...)
  context/     AuthContext (token + role), ThemeContext (dark mode)
  store/       cartStore.js (Zustand — POS cart)
  components/  shared: RoleGuard, NavRail, ScreenTopbar, ToastStack, XAFAmount, ...
  features/    one folder per screen: auth, setup, pos, receipt,
               inventory, sales, suppliers, dashboard
```

Conventions:

- `api/client.js`: token in localStorage (`bledger_token`), `Authorization: Token`, 401 interceptor dispatches `bledger:unauthorized` (AuthContext listens — avoids a circular import).
- Routing (`App.jsx`): every route is wrapped in `RequireSetupComplete` (gates on `GET /setup/status/`) and `RequireAuth`. `/suppliers` additionally uses `RoleGuard minimumRole="manager"` (redirects cashiers to `/pos`); `/dashboard` deliberately does not — cashiers get a stock-alerts-only view.
- `NavRail` is `position: fixed`, rendered once at App root — screens keep their own `height:100vh` chains (`screen-layout.css`); room is made with padding, not a layout wrapper. Nav items are role-filtered.
- List filtering is largely client-side (POS grid, suppliers' purchase list) — no DjangoFilterBackend/SearchFilter anywhere; the one server-side filter set is Sales History's hand-parsed query params, which silently ignore bad values.
- Reusable side-drawer panel pattern for add/edit forms (Inventory's ProductFormPanel, Suppliers' SupplierFormPanel).

---

## 5. Known gotchas (hard-won — don't rediscover these)

- Chromium bug: sticky `<th>` + `border-collapse` loses borders on scroll — tables use `border-collapse: separate`.
- Never `display:flex` directly on `<td>` — wrap contents in a div.
- `?format=` is reserved by DRF — don't use it as a custom query param.
- `screen-layout.css` groups selectors in comma lists — a missing comma silently breaks every screen in the group; re-verify commas on every edit.
- WeasyPrint import is lazy and failure-tolerant (`pdf_backend.py`) — missing system libs must 503 the printing endpoints, never crash startup.

---

## 6. Known limitations & open items (Phase 1 close-out)

Remaining (deferred to Phase 2 by design):

- Phase 2 sync engine (`sync/engine.py`, `pull.py`, `conflict.py`, `tasks.py`) not yet built — only the outbox table, registry, and writer exist.

Resolved in Phase 2 Stage 1 (see `docs/PHASE2_DESIGN.md` §8):

- ~~Outbox coverage is partial~~ — Product create/edit and all Category writes now emit entries. `apps/sync/registry.py` declares every table as either synced (with a payload schema version) or explicitly never-synced, and a test fails the build if a new `BaseModel` is left unclassified.
- ~~Outbox payload had no contract~~ — `serialize_instance()` applies per-type rules and `OutboxEntry.schema_version` records which contract each entry was written against.
- ~~`Sale.reference` would collide across branches~~ — now `BLD-<branch_code>-<year>-<seq>`, with `Branch.code` unique per branch.
- ~~`soft_delete()` dropped its version increment~~ — `update_fields` now includes `"version"`.

Resolved during Phase 1 close-out (kept for the record):

- ~~Sale reference race~~ — `SaleSerializer` now derives the next `BLD-YYYY-NNNN` from the most recently created reference and retries on `IntegrityError` (the `reference` column is unique), instead of count-then-format.
- ~~`version`/`updated_at` on stock moves~~ — every stock write (adjustment, sale, void, purchase) now persists `["stock_level", "updated_at", "version"]` via instance `save()`; void no longer bypasses `save()` with a queryset `.update()`.
- ~~`Supplier.is_active` unsurfaced~~ — Suppliers screen now has Deactivate (with inline confirm) / Reactivate, an Inactive badge in list + detail, and a disabled Record-purchase button for inactive suppliers; `PurchaseSerializer.validate()` enforces the same rule server-side.
- ~~Suppliers `<720px` stopgap~~ — small viewports now get a one-panel-at-a-time flow: list by default, detail on selection, back button to return.
- ~~Unprefixed classes in `LoginScreen.css` / `SetupWizard.css`~~ — verified fully `login-`/`wiz-` prefixed (done in an earlier session).
- ~~POS/Receipt Banner→toast migration~~ — verified done in an earlier session; this pass removed a leftover unused `Banner` import in `ReceiptScreen.jsx` and routed void-sale failures through a toast (previously an unhandled rejection). The remaining `Banner` uses (products/suppliers failed to load) are deliberate: persistent blocking states, not transient action feedback.

---

## 7. Working conventions

- One app/screen per work session; verify against real source, not design docs or summaries alone — `Bledger_UI_Design_Reference.docx` for anything screen-level (its own rule: live-project customizations win over the doc for anything already built).
- Deviations from design docs are fine when the schema/backend says otherwise (e.g. the purchases table has no "Ref" column because `Purchase` has no reference field) — but flag them explicitly.
- Money: always integers, always through `format_xaf`/`round_xaf` (backend) or `XAFAmount` (frontend).
- New synced models: inherit `BaseModel`, add outbox writes in the same transaction as every mutation, filter by `request.branch_id`.
- New endpoints: pick the matching permission class, follow the immutability conventions above, and set `include_format_suffixes = False` on any new router.
