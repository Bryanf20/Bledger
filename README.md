# Bledger

**Business management and point-of-sale for Cameroonian SMEs.**

Built for retail shops, boutiques, and provision stores — designed to work
perfectly with no internet, on low-spec hardware, in XAF.

[Design docs](#documentation) · [Current status](#current-status) · [Quick start](#quick-start) · [Roadmap](#roadmap)

---

## Why Bledger

Most business software assumes reliable internet, decimal currency, fixed
prices, and modern hardware. In the Cameroonian retail market, none of those
hold. Bledger is built the other way round:

- **Offline is the normal state, not an error.** Every write goes to a local
  database first. A shop can trade for a week with no connection and lose
  nothing.
- **XAF is a whole-number currency.** Every monetary value in the system is an
  integer. There are no cents to round, and no floating-point money anywhere.
- **Prices are negotiated.** Haggling (*marchandage*) is normal, so the data
  model records the catalogue price, the price actually paid, and the variance
  between them on every single line item.
- **Mobile Money is a first-class payment method**, alongside cash — not an
  afterthought bolted on to a card-centric design.
- **Hardware is modest.** Small bundles, minimal background services, and a
  desktop build measured in megabytes rather than hundreds of them.

## What Bledger does

**Point of sale** — Fast product grid with search and category filters. Cart
with automatic bulk pricing. Cash, MTN MoMo, Orange Money, and other payment
methods, with reference capture and confirmation for Mobile Money. Hold a sale
to serve another customer and restore it later. Negotiated pricing with
configurable discount floors and surplus ceilings, and manager approval beyond
them.

**Inventory** — Products with retail and bulk pricing, categories, units, stock
levels, and low-stock thresholds. Stock never moves by direct edit: every change
is a sale, a purchase, or an explicit adjustment with a reason and a full audit
trail. Products deactivate rather than delete, so historical receipts stay
correct. Barcode scanning at the till and during stock intake.

**Sales & receipts** — 80mm receipts as PDF (and thermal ESC/POS from Phase 3),
designed at receipt width from day one. Full sales history with date, payment
method, and status filters. Voiding restores stock and keeps a permanent audit
record of who voided what and why.

**Suppliers & purchases** — Supplier directory and purchase history. Recording a
purchase increments stock in the same transaction — one action, not two. Payment
status tracking (paid, partial, credit) with an append-only payment ledger, so
the owner always knows what is still owed.

**Customers & credit** — Customer directory with credit limits, balances derived
from an append-only ledger, and an aged-debt report — because *"na go pay you
Friday"* is a real and common transaction that most software cannot represent.

**Owner dashboard** — Revenue, transaction count, and average sale with
period-over-period comparison. Sales by hour or day. Payment method breakdown.
Top products. Live stock alerts. Variance reporting showing surplus collected
and discounts given, broken down per cashier. Exportable reports.

**Multi-branch** — Each branch runs independently offline and syncs to a central
cloud when connected. The owner sees every branch from one dashboard. The
product catalogue is owned centrally and pushed to branches read-only, with
local price overrides for regional variation.

**Roles** — Owner, manager, and cashier, enforced consistently in the API rather
than merely hidden in the UI. Cashiers sign in with a 4-digit PIN for fast shift
changes; owners and managers use a password.

## Deployment modes

Bledger ships in two configurations from one codebase.

| | **Mode 2 — Standalone** | **Mode 1 — Connected** |
|---|---|---|
| **For** | A single shop | A business with several branches |
| **Database** | SQLite, on the device | SQLite per branch + central PostgreSQL |
| **Internet** | Never required | Never required to *operate*; used to sync |
| **Sync** | Disabled | Outbox engine, pushes and pulls in the background |
| **Licensing** | One-time license | Per-branch subscription |

The important property in both modes: **no user action ever waits on the
network.** Connectivity affects when data replicates, never whether a cashier
can complete a sale.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 6.0 + Django REST Framework |
| Frontend | React 19 + Vite |
| Local database | SQLite |
| Cloud database | PostgreSQL |
| Background tasks | `django.tasks` (Django 6.0 native) |
| PDF / receipts | WeasyPrint, 80mm templates |
| Desktop shell | Tauri *(Phase 3)* |
| Hosting | Railway → DigitalOcean at scale |

## Roadmap

Bledger is built in five phases. Each one is a shippable product, not a
checkpoint.

### Phase 1 — MVP web app - Complete

Standalone mode end to end: authentication and roles, first-run setup wizard
with starter product templates, inventory, POS, receipts, sales history,
suppliers and purchases, and the owner dashboard. SQLite only, PDF receipts,
English. Sale line items store catalogue price, actual price, and variance from
day one so negotiated pricing needs no migration later.

### Phase 2 — Cloud, sync & haggling ◐ In design

PostgreSQL and the outbox sync engine. Mode 1 goes live with multi-branch
deployment and an aggregated HQ dashboard. Negotiated pricing UI with floor and
ceiling controls, PIN approval, and variance reporting. Customer accounts and
credit. Barcode scanning. A full settings module.

### Phase 3 — Desktop app

Tauri wrapper with packaged installers for both modes. Thermal ESC/POS receipt
printing — a configuration switch, not an application rewrite, because printing
has been behind an abstraction since Phase 1. Mobile Money API integration
begins. USB-based update mechanism for shops with no reliable connection.

### Phase 4 — Compliance & expansion

HR and payroll including CNPS contributions. OHADA-standard financial
statements. French localisation — the i18n infrastructure has been in place
since the first line of code. Expansion into the wider Francophone market.

### Phase 5 — Scale & optimise

Migration to DigitalOcean or a local African host. Celery and Redis if sync load
demands more than `django.tasks` provides. Advanced analytics. Community-
contributed product templates.

## Current status

> **Phase 1 is complete. Phase 2 is designed and awaiting implementation.**

**Shipped (Phase 1)**

- All 8 backend apps: `core`, `auth_users`, `inventory`, `sales`, `printing`,
  `suppliers`, `dashboard`, and the `sync` scaffold.
- All 7 screens: Login/PIN, Setup Wizard, POS, Receipt, Inventory, Sales
  History, Suppliers & Purchases, plus the Owner Dashboard and a persistent
  navigation rail.
- Light and dark themes, toast notifications, role-aware routing.
- Supplier payment ledger, purchase payment tracking, supplier
  deactivation/reactivation.

**Not yet built**

- The sync engine itself. `OutboxEntry` and the outbox writer exist and are
  wired into most mutations, but nothing drains the queue yet — by design, since
  Phase 1 targets standalone deployment.
- Outbox coverage is deliberately incomplete: product create/edit and category
  writes do not yet emit outbox entries. This is tracked as blocking work for
  Phase 2.
- Everything else in Phase 2 and beyond.

**Known Phase 2 blockers**, documented in
[`docs/PHASE2_DESIGN.md`](docs/PHASE2_DESIGN.md):

- `Sale.reference` is globally unique but generated per-install, so branches
  would collide in a shared database. Needs a branch discriminator.
- The outbox payload has no versioned serialization contract.
- Customer credit needs an architectural decision on whether customers are
  scoped per branch or shared across them.

## Quick start

**Requirements:** Python 3.12+, Node 20+.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp ../.env.example ../.env          # then edit as needed
export DJANGO_SETTINGS_MODULE=bledger.settings.development
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev                          # proxies /api/* to :8000
```

Open the app and complete the first-run setup wizard to create your business and
owner account.

### Tests

```bash
cd backend
DJANGO_SETTINGS_MODULE=bledger.settings.testing pytest
```

```bash
cd frontend
npm run lint
```

> **Note:** PDF receipts and report exports require WeasyPrint's system
> libraries (Pango, Cairo, GDK-PixBuf). If they are missing, those endpoints
> return a clear 503 and the rest of the application is unaffected.

### Settings modules

| Module | Database | Purpose |
|---|---|---|
| `development` | SQLite | Local development, CORS open to the Vite dev server |
| `standalone` | SQLite | Mode 2 production — sync disabled |
| `connected` | PostgreSQL | Mode 1 cloud server — sync enabled |
| `production` | PostgreSQL | Inherits `connected`, adds security hardening |
| `testing` | In-memory SQLite | Fast test runs |

## Project layout

```
backend/
  bledger/
    settings/            base · development · standalone · connected · production · testing
    urls.py              mounts every app under /api/v1/
  apps/
    core/                BaseModel, permissions, pagination, middleware, XAF helpers
    auth_users/          Branch, BledgerUser, login/PIN auth, setup wizard
    inventory/           products, categories, stock adjustments, price overrides, templates
    sales/               POS sales, line items, held sales, voids, receipt data
    printing/            printer abstraction — PDF now, thermal in Phase 3
    suppliers/           supplier directory, purchases, payment ledger
    dashboard/           aggregates, KPIs, reports
    sync/                outbox model and writer — engine lands in Phase 2
frontend/
  src/
    api/                 axios client, one module per backend app
    hooks/               React Query wrappers
    context/             auth and theme
    store/               Zustand cart store
    components/          shared UI
    features/            one folder per screen
docs/
  USER_GUIDE.md          for shop owners, managers, and cashiers
  DEV_GUIDE.md           architecture, conventions, gotchas
  PHASE2_DESIGN.md       full Phase 2 design across all workstreams
```

## Documentation

| Document | Audience |
|---|---|
| [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) | Shop staff — how to sell, manage stock, handle suppliers |
| [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md) | Developers — architecture, conventions, known gotchas |
| [`docs/PHASE2_DESIGN.md`](docs/PHASE2_DESIGN.md) | Phase 2 design across all six workstreams |
| `Bledger_Design_v0.5.docx` | Full product and screen design |
| `Bledger_Feasibility_Design_v0.3.docx` | Technical feasibility, architecture, roadmap |
| `Bledger_UI_Design_Reference.docx` | Screen-level implementation baseline |

## Architectural commitments

These are settled decisions. They are documented here because reversing any of
them is expensive, and because they explain choices that would otherwise look
arbitrary.

- **Money is always an integer.** XAF has no practical subunit. Every monetary
  field is `PositiveIntegerField`; formatting and rounding live in exactly one
  module.
- **Local write first, outbox second, cloud third.** In that order, in one
  transaction. This is what makes offline operation reliable rather than
  best-effort.
- **Financial records are immutable.** Sales and purchases have no update or
  delete route. Corrections happen through purpose-built, auditable actions —
  void a sale, record a payment — which append records rather than rewriting
  them.
- **Stock moves through exactly four code paths.** Adjustments, sales, voids,
  and purchases. Each locks the product row inside a transaction. Nothing else
  is permitted to change a stock level.
- **Branches own their own records.** No two branches can edit the same row.
  The product catalogue is the single shared layer, owned centrally and
  distributed read-only.
- **Printing is an abstraction.** The application calls one function. Swapping
  PDF for thermal output is a configuration change.

## Contributing

Bledger is under active single-developer development. Read
[`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md) before making changes — particularly
the conventions on stock mutation, outbox writes, and money handling, which are
load-bearing rather than stylistic.
