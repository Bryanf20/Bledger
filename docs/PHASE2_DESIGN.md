# Bledger Phase 2 — Complete Design

**Status:** design proposal, pending review
**Supersedes:** the sync-only draft of this document
**Covers:** all seven Phase 2 workstreams — cloud sync & multi-branch, negotiated pricing, customer accounts & credit, barcode scanning, purchase orders & supplier payments, the settings module, and cost tracking & profitability.

Phase 1 (standalone POS, 8 backend apps, 7 screens) is complete. This document defines everything Phase 2 adds.

---

## 0. How to read this document

Sections are marked by how much prior commitment exists:

- **[DOC]** — specified in `Bledger_Feasibility_Design_v0.3` or `Bledger_Design_v0.5`. Design here follows that spec.
- **[PROPOSED]** — the design docs list the module as Phase 2 but give only a one-line description. Everything here is a proposal for your review, not a committed decision.

Workstream A (sync) and B (negotiated pricing) are largely **[DOC]**. Workstreams C–G are largely **[PROPOSED]**. Workstream G has no doc grounding at all — it was identified by review during Phase 2 design and is included because its absence blocks any profit reporting.

---

## 1. Scope and governing principles

| # | Workstream | Doc grounding | Depends on |
|---|---|---|---|
| **A** | Cloud sync & multi-branch | [DOC] §5, §6, §8 | — |
| **B** | Negotiated pricing (haggling) | [DOC] §10 | — (data model already in place) |
| **C** | Customer accounts & credit | [PROPOSED] | Sales module (stable) |
| **D** | Barcode scanning | [PROPOSED] | — |
| **E** | Purchase orders & supplier payments | [PROPOSED] | Suppliers module (stable) |
| **F** | Settings module | [PROPOSED] | Touches all of the above |
| **G** | Cost tracking & profitability | [PROPOSED] | Inventory + suppliers (stable) |

Three principles carry through every workstream:

1. **Offline-first is non-negotiable.** No user action waits on the cloud (feasibility §8.1). Every new feature must work with the network down.
2. **Money stays integer XAF.** Every new monetary field is `PositiveIntegerField` (or `IntegerField` where signed, as with variance). Never `Decimal`.
3. **Every new synced table follows the existing contract.** Inherit `BaseModel`, write an `OutboxEntry` in the same transaction as every mutation, scope queries by `request.branch_id`.

Principle 3 is what keeps workstreams C–E from becoming sync liabilities later. Any new model added without it is a bug the moment Mode 1 goes live.

---

## 2. Workstream A — Cloud sync & multi-branch **[DOC]**

Phase 1 shipped **Mode 2 (Standalone)**: one shop, one device, SQLite, no internet. This adds **Mode 1 (Connected)**: several branches, each still fully offline-capable on its own SQLite, with central PostgreSQL aggregating everything.

### 2.1 Why this is tractable

Per feasibility §6, **branches never share editable records**. No two branches modify the same row, so there is no general merge problem. There is exactly one shared layer — the HQ product catalogue, pushed down read-only. That reduces distributed conflict resolution (hard) to one-way catalogue propagation plus append-only replication (manageable).

Workstream C (customer credit) is the one thing that threatens this assumption — see §4.4.

### 2.2 Architecture

Decision: **sync lives inside the existing Django project**, not a separate FastAPI service as feasibility §7 suggested. One codebase, one deploy, reuses existing models/auth/permissions. SME branch volume is a few hundred rows a day; async throughput is not the constraint. Extract later if that changes.

```
Branch device (Mode 1)                        Cloud (Railway / DigitalOcean)
┌────────────────────────────┐                ┌──────────────────────────────┐
│ Django + SQLite            │                │ Django + PostgreSQL          │
│  • POS, inventory, etc.    │                │  • same codebase,            │
│  • writes → local DB       │  push (30s)    │    settings.connected        │
│  • writes → OutboxEntry    │ ─────────────► │  • source of truth across    │
│    (same transaction)      │                │    branches                  │
│  • sync engine drains      │  pull (30s)    │  • HQ dashboard reads here   │
│    outbox                  │ ◄───────────── │                              │
└────────────────────────────┘                └──────────────────────────────┘
```

**Third settings module needed.** Today `standalone.py` (SQLite, sync off) and `connected.py` (Postgres, sync on) exist, but `connected.py` describes *the cloud*, while a branch device in Mode 1 is a third thing: SQLite locally **and** sync on.

| Module | DB | SYNC_ENABLED | Role |
|---|---|---|---|
| `standalone.py` | SQLite | False | Phase 1 single-shop install (unchanged) |
| `branch.py` *(new)* | SQLite | True | Mode 1 branch device |
| `connected.py` | PostgreSQL | True | The cloud server |

### 2.3 Branch identity and enrolment

**The biggest gap in current code.** `BRANCH_ID` is a static string in `.env` (`default="HQ"`), stamped on requests by `DeploymentContextMiddleware`. Fine for one install; unworkable for multi-branch — a branch needs a cloud-issued identity plus credentials to authenticate pushes, and nothing stops two installs claiming the same ID.

Proposed enrolment flow:

1. Owner creates a branch in the HQ dashboard → cloud returns a one-time, expiring **enrolment code**.
2. On the new device, the setup wizard gains a "Connect to head office" path; the manager enters the code.
3. Device POSTs to `/api/v1/sync/enrol/`. Cloud validates, consumes the code, returns the canonical `branch_id` (UUID), a long-lived **device sync token**, and branch config.
4. Device persists these. `BRANCH_ID` becomes a value read from the local `Branch` row, not an env constant.

Model changes: `Branch` gains `is_hq`, `cloud_id`, `sync_token` (write-only), `last_synced_at`, `is_active`, `code` (short, for references — see §7.1). New cloud-side `EnrolmentCode` model. `DeploymentContextMiddleware` reads from the `Branch` row, falling back to `settings.BRANCH_ID` so standalone is unaffected.

### 2.4 Sync protocol

Two cloud-side endpoints, authenticated by **device sync token** (not a user token — sync must work with nobody logged in).

**`POST /api/v1/sync/push/`** — batch of outbox entries; response reports per-entry outcome so one poison row can't block the queue:

| Status | Meaning | Branch does |
|---|---|---|
| `applied` | Written to cloud | Set `synced_at`, stop |
| `duplicate` | Already applied | Same as `applied` |
| `rejected` | Permanently invalid (bad FK, schema mismatch) | Record `last_error`, stop retrying, surface to owner |
| *(5xx / timeout)* | Transient | Increment `attempted`, retry with backoff |

**Idempotency is mandatory** — a branch that pushes successfully but loses the response will re-push. Unique index on `(branch_id, outbox_id)` in a cloud `AppliedEntry` table, checked inside the applying transaction.

**`GET /api/v1/sync/pull/?since=<server_timestamp>`** — returns what this branch needs: HQ catalogue (`Product`, `Category`), tombstones for soft-deleted catalogue rows, `BledgerUser` rows for this branch, and branch config changes. A branch never pulls another branch's sales or stock — aggregation is the HQ dashboard's job, reading cloud Postgres directly.

`since` uses the **server's** clock (returned as `server_time` on every response, stored locally), never the device's. Field device clocks aren't trustworthy.

### 2.5 Conflict rules

| Situation | Rule | Rationale |
|---|---|---|
| Branch pushes sale/purchase/adjustment | Always accept (append-only) | Facts that already happened at the till |
| HQ edits catalogue vs. branch's unpushed edit | HQ wins | Catalogue is HQ-owned; branches may only add `BranchPriceOverride` |
| Two branches set a price override | No conflict | Unique per `(product, branch)` — separate rows |
| Same record pushed twice | Idempotent no-op | §2.4 |
| Stock levels | Never synced as absolute values | Below |

**Stock is derived, not synced.** `Product.stock_level` must not replicate as an absolute number — two branches pushing `stock_level = 40` is meaningless, and HQ's aggregate is a sum, not a winner. Stock movements (`StockAdjustment`, sale lines, purchase lines) sync as the append-only events they already are; HQ stock figures are computed per branch from those events. This matches the feasibility doc's own delta-sync definition. Local `stock_level` stays exactly as-is for the branch's fast reads.

### 2.6 Connectivity UX

Four states from feasibility §5. The topbar's `screen-sync-dot` is currently hardcoded to "Synced" — Phase 2 makes it real.

| State | Indicator | Detail |
|---|---|---|
| Fully online | Green ● Synced | Last sync time on hover |
| Degraded | Amber ● Syncing… | Pending-changes count |
| Fully offline | Red ● Offline | "Last synced 2h ago" |
| Reconnection | Toast: "X changes synced" | Catalogue updates applied |

`useSyncStatus` hook polling local `GET /api/v1/sync/status/`, plus a `SyncStatusBadge` replacing the hardcoded dot. Never blocks interaction — offline is a normal working state, not an error. Also needed: an owner-facing sync health view (pending, rejected-with-reasons, per-branch last-seen). Rejected entries are silent data loss unless someone can see them.

### 2.7 Background execution

Django 6.0's native `django.tasks` (locked decision, superseding the doc's Django-Q2/Celery plan). Periodic task per device: drain outbox → push in batches of ~100; pull since last `server_time`; apply; record results. 30s cadence online, exponential backoff to ~15 min ceiling when failing, immediate flush on reconnect. Must hold a lock so overlapping runs can't double-push.

---

## 3. Workstream B — Negotiated pricing (haggling) **[DOC §10]**

Haggling (*marchandage*) is embedded in Cameroonian retail. A cashier may quote above catalogue and negotiate down, or discount below it. Both surplus and discount must be tracked to prevent cash leakage and give the owner a true picture of the till.

**The data model already exists.** `SaleLineItem` has carried `catalogue_price`, `actual_price`, `variance`, and `variance_approved_by` since Phase 1 precisely so this needs no migration. Currently `actual_price == catalogue_price` and `variance == 0` are hardcoded in `SaleSerializer.create()`.

### 3.1 Floor/ceiling configuration

New: per-product and per-category discount floor and surplus ceiling, expressed as percentages.

- `Category` gains `discount_floor_pct`, `surplus_ceiling_pct` (nullable).
- `Product` gains the same two fields (nullable), overriding its category.
- Business-wide defaults live in the settings module (§6) as the final fallback.

Resolution order: product → category → business default. A helper `resolve_price_bounds(product)` in `apps/sales/services.py` alongside the existing `resolve_unit_price()`.

### 3.2 POS behaviour

| Scenario | Action required |
|---|---|
| At catalogue price | None |
| Below catalogue, within floor | Cashier proceeds freely |
| Below catalogue, beyond floor | Owner/manager PIN required |
| Above catalogue, within ceiling | Cashier proceeds freely |
| Above catalogue, beyond ceiling | Owner/manager PIN required |

The cart line gains an editable unit price. Variance shows inline (green for surplus, amber for discount) with the percentage. When a variance breaches its bound, an approval step appears — a manager/owner enters their PIN, and on success `variance_approved_by` records **the approver**, not the cashier.

`BledgerUser.check_pin()` already exists and is used for cashier login. Approval reuses it, but needs a new endpoint: `POST /api/v1/auth/verify-pin/` returning whether the PIN belongs to a manager-or-above **without** creating a session or token. Critically it must not log the cashier out or switch the session — this is an authorisation check inside another user's session, a different operation from login.

**Rate-limit this endpoint.** It's a 4-digit-PIN oracle; without throttling it's brute-forceable in ~10,000 tries. Suggest lockout after ~5 failures per user per few minutes, and log every attempt.

### 3.3 Server-side enforcement

Client-side bounds are a UX affordance, not a control. `SaleSerializer.create()` must:

1. Compute `catalogue_price` via existing `resolve_unit_price()` — never trust a client-supplied catalogue price.
2. Accept `actual_price` per line from the client.
3. Compute `variance = actual_price - catalogue_price` server-side.
4. Resolve bounds; if breached, require a valid `variance_approval_token` (short-lived, issued by `/verify-pin/`) and record the approver.
5. Reject the sale if a bound is breached without valid approval.

Without step 5 the entire control is decorative — a modified client could send any price.

### 3.4 Reporting (feasibility §10.3)

New dashboard endpoints: total surplus per period, total discounts per period, net variance, per-cashier breakdown, and end-of-day reconciliation (expected cash = Σ catalogue prices vs actual cash = Σ actual prices).

The per-cashier breakdown is the fraud-detection surface and should be prominent for owners. A cashier consistently discounting to the floor deserves a look.

---

## 4. Workstream C — Customer accounts & credit **[PROPOSED]**

The docs specify only: *"Customer ledger, credit limits, debt tracking, aged debt report."* Everything below is proposal.

Selling on credit (*"na go pay you Friday"*) is ubiquitous in Cameroonian retail and currently invisible to Bledger — a credit sale either isn't recorded or is recorded as if paid, which corrupts the day's cash figures.

### 4.1 Models

```
Customer(BaseModel)
  name, phone, area, notes, is_active
  credit_limit (PositiveIntegerField, 0 = no credit allowed)
  → balance (derived, not stored — see §4.3)

CustomerPayment(BaseModel)      # append-only, mirrors PurchasePayment
  customer FK, amount, payment_date, payment_method,
  recorded_by FK, note
```

`Sale` gains `customer` (nullable FK) and a `credit` payment method. A credit sale records the full amount as owed; partial payment at time of sale is `amount_tendered` with the remainder on account.

This deliberately mirrors the existing supplier-side design (`Purchase` / `PurchasePayment` / `payment_status`), which is already proven and which staff will recognise. Suppliers = money we owe; customers = money owed to us.

### 4.2 Credit limit enforcement

At POS, selecting a customer shows their current balance and remaining credit. A sale that would exceed `credit_limit` requires manager/owner approval — reusing the same PIN-approval mechanism built for haggling (§3.2). One approval primitive, two uses.

### 4.3 Balance is derived, never stored

`customer.balance = Σ(credit sales) − Σ(payments)`. Storing a running total invites the classic drift bug where the stored figure and the ledger disagree and nobody knows which is right.

This differs from `Purchase.amount_paid`, which *is* a stored running total. That was acceptable because it's scoped to a single purchase with a bounded payment list. A customer balance spans unbounded sales and payments over years — and, in Mode 1, potentially across branches, where a stored total would be a genuine conflict surface (§4.4). Derive it.

For performance, an aggregate query per customer is fine at SME scale; add a materialised balance later only if profiling demands it.

### 4.4 ⚠ Credit breaks the "no shared records" assumption

**This needs your decision before implementation.** Feasibility §6 states branches never share editable records — the foundation that makes sync tractable (§2.1). A customer with credit at *two* branches breaks that: both branches would mutate one customer's balance, which is exactly the conflict case the architecture was designed to avoid.

Three options:

| Option | Behaviour | Cost |
|---|---|---|
| **Branch-scoped customers** *(recommended)* | A customer belongs to one branch; credit is per-branch. Two branches = two records. | Preserves the sync model completely. Slightly odd if a real customer uses both branches. |
| **Shared customers, branch-scoped credit** | One customer record (HQ-owned, like the catalogue), but balances tracked per branch. | Middle ground; customer identity is shared, money is not. More complex pull logic. |
| **Fully shared credit** | One balance across all branches. | Requires real distributed conflict resolution. Would compromise the architecture for an edge case. |

Recommendation: **branch-scoped customers**. It keeps the architecture intact, and a customer holding credit at two branches of a small provision-store chain is rare. If it later proves common, option 2 is a migration, not a rewrite.

### 4.5 Screens

New **Customers** screen, master-detail, closely mirroring Suppliers: directory on the left, detail on the right with balance, credit limit, sale history, payment history, and a record-payment form. Manager+ for credit-limit edits; cashiers may select a customer at POS and see the balance but not change limits.

Also: aged-debt report (0–30 / 31–60 / 60+ days) on the dashboard, and customer balance on printed receipts for credit sales.

---

## 5. Workstream D — Barcode scanning **[PROPOSED]**

Docs specify: *"USB or camera-based barcode scanning at POS and during stock intake."* The POS already has a **deliberately disabled barcode button**, placed in Phase 1 so the UI wouldn't need rework later (`Bledger_Design_v0.5`, POS screen notes; visible in `POSScreen.jsx` as the `disabled title="Phase 2"` button) — this activates it.

### 5.1 Model

`Product` gains `barcode` (CharField, indexed, nullable, unique per branch when set). Nullable because most Cameroonian provision-store goods — rice sold by the bag, sachet water, loose produce — have no barcode at all. **Barcode must remain an optional accelerator, never a required field**; a design that assumes every product has one won't survive contact with the actual market.

### 5.2 USB scanners first

USB barcode scanners are HID keyboard-emulation devices: they "type" the code and press Enter. No driver, no permissions, no library — they work today with a focused text input.

Implementation is a `useBarcodeInput` hook detecting the scanner's signature (rapid character bursts terminated by Enter, far faster than human typing) and distinguishing it from someone typing in the search box. On match: add product to cart directly. On no match at POS: offer to search manually. On no match at stock intake: offer to create the product with that barcode pre-filled.

### 5.3 Camera scanning second

Camera scanning (via a library such as `zxing-js` or the native `BarcodeDetector` API) is a bigger lift: camera permissions, HTTPS requirement, lower reliability under poor lighting, and real performance cost on the low-spec hardware this product targets. Recommend shipping USB first, treating camera as a follow-on — it's a genuinely separate piece of work and USB covers the till counter, which is where the volume is.

### 5.4 Where it applies

POS (add to cart), inventory (find product), stock intake / record purchase (add line item), and product create/edit (assign barcode).

### 5.5 Implementation notes (Stage 2, step 3 — ✅ done)

USB scanning shipped; camera (§5.3) and stock-intake scan-to-add-line remain follow-ons.

- **`Product.barcode`** — `CharField(max_length=64, blank, db_index)`, optional. A partial `UniqueConstraint` on `(branch_id, barcode)` excludes the empty string and soft-deleted rows, so any number of products may carry no barcode while set ones are unique per branch (and the *same* manufacturer code may legitimately exist at a different branch). Exposed on `ProductSerializer` with a `validate_barcode` that turns the would-be `IntegrityError` into a clean 400. Migration `inventory.0004_product_barcode`.
- **No schema-version bump.** Barcode joins the `inventory_product` payload, but the sync engine isn't built and no cloud has consumed the v1 contract yet, so v1 is simply redefined to include it rather than bumped to v2 (§8.3). Product writes still emit outbox entries, now carrying `barcode` — covered by a test.
- **`useBarcodeInput` hook** (`frontend/src/hooks/`) — global keydown listener that tells scanner from typist purely by speed: a burst of characters each within `maxIntervalMs` (40ms) of the last, terminated by Enter, of at least `minLength` (3). The terminal Enter is `preventDefault`ed on a recognised scan so it can't submit a form. Accepted rough edge: if a field is focused mid-scan the digits also land in it — documented in the hook.
- **POS scan-to-cart** — the previously-disabled barcode button is now a scanning on/off toggle (default on). A scan resolves the code against a client-side barcode→product map (same "fetch all, resolve locally" convention as the rest of POS), then adds to cart with the same stock ceiling `addItem` enforces, or shows a toast (no match / inactive / out of stock / would exceed stock). Scanning is suspended while a modal or confirm is open.
- **Product form** — a barcode input on create/edit; server-side duplicate errors surface via the existing toast path.
- **Verification** — backend fully tested (`inventory/tests/test_barcode.py`, 7). Frontend transform-checked as valid JSX/ESM via esbuild but **not** run through `npm run build`/`oxlint` (the sandbox has no project `node_modules`); do that in WSL.

---

## 6. Workstream E — Purchase orders & supplier payments **[PROPOSED]**

Docs list *"PO workflow"* and *"Supplier payments"* as Phase 2. **Supplier payments already shipped in Phase 1** — `PurchasePayment`, the record-payment action, and the payment ledger are all built and working. So this workstream reduces to the PO workflow.

### 6.1 The gap

Today a `Purchase` records goods that have *already arrived* — it immediately increments stock. There's no way to represent "I've ordered 20 bags of rice from Eto'o Supplies, arriving Thursday."

### 6.2 Model

```
PurchaseOrder(BaseModel)
  supplier FK, order_date, expected_date,
  status: draft | sent | partially_received | received | cancelled
  notes, created_by FK

PurchaseOrderLineItem(BaseModel)
  purchase_order FK, product FK,
  quantity_ordered, quantity_received, unit_cost
```

**A PO does not touch stock.** Only receiving does. Receiving a PO (fully or partially) creates a normal `Purchase` linked to the PO, which increments stock through the existing proven path. This keeps one and only one code path that moves stock — the existing `select_for_update()` + atomic pattern — rather than adding a second.

Partial receipt is the case that matters: suppliers routinely deliver 15 of 20 bags. `quantity_received` accumulates per line; status derives from whether all lines are complete.

### 6.3 Screens

Extends the existing Suppliers screen rather than adding a new one: a "Purchase orders" tab beside purchase history, PO detail with a receive action, and an "expected deliveries" widget on the dashboard.

### 6.4 Is this actually needed?

Worth questioning. PO workflow is enterprise-flavoured, and a provision-store owner who phones a supplier and writes the order in a notebook may not use it. Given the effort, this is the workstream I'd most readily defer to Phase 3 in favour of credit and barcode, which have clearer daily value. Flagged for your call.

---

## 7. Workstream F — Settings module **[PROPOSED]**

Docs list *"Full settings module (Phase 2)"* against the first-run wizard. Today, business config is set once in the wizard and never editable — there's no way to change a receipt footer, phone number, or business name after setup, which is a real gap independent of everything else here.

### 7.1 Sections

| Section | Contents | Role |
|---|---|---|
| **Business** | Name, branch name, address, phone, receipt footer | Owner |
| **Staff** | List/create/edit/deactivate users, reset PINs | Owner |
| **Pricing** | Business-wide discount floor / surplus ceiling defaults (§3.1), price-deviation alert threshold | Owner |
| **Credit** | Default credit limit, aged-debt thresholds | Owner |
| **Sync** | Connection status, branch identity, enrolment, sync health (§2.6) | Owner |
| **Devices/Branches** | Branch list, enrolment codes, deactivate a device | Owner (HQ) |
| **Printing** | Printer backend, receipt template preview | Manager+ |
| **Appearance** | Theme (already exists as a toggle — belongs here too) | All |

### 7.2 Backend

Most of this edits the existing `Branch` model, which currently has no update endpoint — `SetupView` creates it and nothing modifies it after. Needs `GET/PATCH /api/v1/settings/business/` (owner-only).

Staff management partially exists: `POST /api/v1/users/` creates staff, but there's no list, edit, deactivate, or PIN-reset endpoint. Those are needed for a usable settings screen.

New business-wide defaults (pricing bounds, credit defaults) need somewhere to live. Recommend a small singleton `BusinessSettings` model rather than scattering fields onto `Branch` — it keeps branch identity separate from business policy, which matters once multiple branches exist and policy is HQ-owned.

### 7.3 Implementation notes (Stage 1, step 2 — ✅ done)

Backend core landed; the frontend Settings screen is a later step.

- **`BusinessSettings`** (`apps/auth_users/models.py`) — singleton (pk pinned to 1, `save()` rewrites the one row rather than ever erroring on a second insert, `.load()` creates-with-defaults on first access). Not a `BaseModel` — nothing branch-scoped or soft-deletable about it. Fields carry the policy defaults later workstreams read: `default_discount_floor_pct` / `default_surplus_ceiling_pct` (B), `price_deviation_alert_pct` (A/§9.3), `default_credit_limit` (C), `margin_alert_pct` (G). All have safe defaults, so the features that consume them need no migration when they land. Added to `apps.sync.registry.NEVER_SYNCED` (HQ-owned policy flows cloud→branch via pull, never branch→cloud).
- **Business config** — `GET/PATCH /api/v1/settings/business/` (owner-only) edits the caller's `Branch`. `code`, `deployment_mode`, and `setup_complete` are read-only; `code` in particular is immutable because it's baked into every existing sale reference (§8.1).
- **Preferences** — `GET/PATCH /api/v1/settings/preferences/` (owner-only) edits the `BusinessSettings` singleton.
- **Staff management** — `GET /api/v1/users/` (list, own branch only), `PATCH /api/v1/users/{id}/` (name/role/is_active; deactivate = `is_active=false`, users are never deleted), `POST /api/v1/users/{id}/reset-pin/`. Two lockout guards return 409: an owner can't deactivate or demote themselves. The owner role can't be assigned via staff editing (ownership transfer is a separate, deliberate act, not a Phase 2 requirement). All owner-only; all scoped to the caller's branch (cross-branch access returns 404).
- **Branch and user edits do not write outbox entries** — both are in `NEVER_SYNCED`. In connected mode users are HQ-owned (pulled down), and branch-config sync direction is decided when Stage 3 lands. Deliberately out of scope here.
- Tests: `apps/auth_users/tests/test_settings.py` (21). Full suite green except the pre-existing WeasyPrint-dependent printing tests.

---

## 7A. Workstream G — Cost tracking & profitability **[PROPOSED]**

No doc grounding — this workstream comes from a review question during Phase 2 design: *what happens when a product's cost and selling price change while older stock is still on the shelf?*

The answer today is that **Bledger cannot tell you**. It reports revenue, never profit.

### 7A.1 What already works — price history on sales

Worth stating clearly, because half of the concern is already solved. `SaleLineItem` snapshots `catalogue_price`, `actual_price`, and `line_total` at the moment of sale. Changing `Product.retail_price` afterwards does **not** alter historical sales — old receipts and sales history keep showing what was actually charged. This was designed in from Phase 1 and needs no change.

Two narrow gaps remain in that guarantee:

**Product names are not snapshotted.** `apps/sales/receipt_data.py` reads `item.product.name` live through the FK, as does `SaleLineItemSerializer.product_name`. Renaming a product therefore rewrites every historical receipt and sales-history row. Prices are frozen; names are not.

*Fix:* store `product_name` on `SaleLineItem` at sale time and read from it everywhere. Same treatment prices already get. Also applies to `PurchaseLineItem`.

**No price-change history.** You can see what a given sale charged, but not what a product was priced at on a date when nothing sold. Raise a price with no sales at the old one and that figure is unrecoverable.

*Fix:* `ProductPriceHistory(BaseModel)` — `product`, `retail_price`, `bulk_price`, `bulk_min_qty`, `changed_by`, `effective_from`. Append a row on every price change. Doubles as an audit trail of who has been moving prices, which is worth having on its own.

### 7A.2 The real gap — there is no cost anywhere

`Product` has **no cost field**. Cost exists only on `PurchaseLineItem.unit_cost`, per delivery, never rolled up. Consequences:

- No cost of goods sold. No gross margin. No profit, per product or overall.
- The dashboard's revenue figures cannot be turned into profit figures by any query.
- Rising supplier costs silently compress margin with nothing surfacing it.

And `Product.stock_level` is a single fungible integer — 50 units, with no record that 20 arrived at 3,000 and 30 at 3,500.

### 7A.3 Decision: weighted average cost

**Chosen: weighted average cost (WAC)**, recomputed on every purchase.

```
Before:   20 bags × 3,000 =  60,000
Restock: +30 bags × 3,500 = 105,000
         ──────────────────────────
          50 bags            165,000  →  average_cost = 3,300
```

Rejected alternatives:

| Method | Why not |
|---|---|
| **FIFO** | Requires lot/batch tracking and forces every sale to decide which lot it drew from. Bags stacked in a store room are physically indistinguishable — the precision is unenforceable in reality, and it complicates the POS for no operational gain. |
| **Latest cost** | Overstates cost of existing stock immediately after a price rise, producing misleadingly low margins on goods bought cheaply. |

WAC is one number per product, explainable to an owner in a sentence, and acceptable under OHADA for Phase 4 accounting.

### 7A.4 Selling price stays a single current value — deliberately

A tempting reading of the original question is that old stock should keep selling at the old price until it runs out. **It should not**, and this is a deliberate non-change.

Real shops sell at today's market price regardless of what a particular unit cost them. Lot-level selling prices would mean the POS asking which batch a bag came from — unusable at a counter, and unenforceable since the goods are physically mixed. The selling price is therefore correctly a single current value on `Product`.

The problem was never the selling price. It was that nothing tracked cost, so the *margin consequence* of a cost rise was invisible. WAC fixes exactly that without touching POS behaviour.

### 7A.5 Model changes

```
Product  + average_cost         PositiveIntegerField, default 0
         + last_cost            PositiveIntegerField, null   (most recent unit_cost, for reference)

SaleLineItem      + unit_cost_at_sale   PositiveIntegerField, default 0
                  + product_name        CharField (§7A.1)

PurchaseLineItem  + product_name        CharField (§7A.1)

ProductPriceHistory(BaseModel)          (§7A.1)
```

**Recompute rule** — inside `PurchaseSerializer.create()`, in the same locked transaction that already increments `stock_level`:

```
new_average = ((stock_before × average_cost) + (qty_received × unit_cost))
              ÷ (stock_before + qty_received)
```

Rounded with the existing `round_xaf()`. Edge cases that must be handled explicitly:

- **Stock at or below zero when restocking** (oversold, or first-ever purchase) — the weighting denominator breaks. Treat as: new average = incoming `unit_cost`.
- **Stock adjustments** — a `remove` adjustment must *not* change `average_cost` (losing stock doesn't change what the rest cost). An `add` adjustment has no cost attached, so it should either inherit the current average or require a cost input. Recommend inheriting, and documenting it.
- **Voided sales** — restoring stock must restore it at the cost it was sold at (`unit_cost_at_sale`), not the current average, or repeated void/resell cycles would drift the average.

**COGS snapshot.** `SaleSerializer.create()` copies the product's `average_cost` at sale time onto `unit_cost_at_sale`, exactly as it already does for prices. Margin history then stays correct forever even as costs move — the same principle that makes §7A.1 work for prices.

### 7A.6 Reporting

New dashboard capability, all derivable once the above exists:

- **Gross margin** per sale, per product, per period — `Σ(line_total) − Σ(unit_cost_at_sale × quantity)`.
- **Margin percentage** and its trend over time.
- **Stock valuation** — `Σ(stock_level × average_cost)`, the money currently sitting on the shelves. Often the single largest asset in these businesses and currently invisible.
- **Margin-squeeze alert** — flag products whose `average_cost` has risen by more than a configurable percentage without a corresponding `retail_price` change. This is the quiet killer of small retail margins and is the most valuable single output of this workstream.
- **Low/negative margin report** — products being sold at or below cost, whether through a cost rise or over-aggressive haggling.

### 7A.7 Interaction with other workstreams

- **Negotiated pricing (B).** Once cost exists, the discount floor becomes far more meaningful — it can be expressed relative to cost rather than to catalogue price, so a cashier can never haggle below cost without approval. Recommend the floor remain percentage-of-catalogue as specified in feasibility §10, but add a hard "never below cost without manager approval" rule on top.
- **Sync (A).** `average_cost` is a *branch-local* derived value — each branch buys at its own prices and must compute its own average. It must **not** be pushed to the cloud as an authoritative catalogue field, for the same reason `stock_level` isn't (§2.5). HQ aggregate margin is computed per branch from synced sale lines, which already carry `unit_cost_at_sale`.
- **Settings (F).** Margin-alert threshold and the "never sell below cost" toggle live in the pricing section.

### 7A.8 Migration

`average_cost` defaults to 0 for existing products, which would report 100% margin — actively misleading. The migration must backfill from purchase history where it exists:

1. For each product with purchases, set `average_cost` to the weighted average of its `PurchaseLineItem` rows.
2. For products with no purchase history (template-loaded or manually created), leave `average_cost` as 0 but **flag them in the UI as "cost not set"** and exclude them from margin reporting rather than reporting a false 100%.
3. Prompt the owner to set costs for flagged products — a one-time task surfaced in Inventory.

Historical `unit_cost_at_sale` cannot be reconstructed and stays 0; margin reporting should therefore start from the deployment date rather than claiming to cover past sales.

---

## 8. Cross-cutting: schema fixes that block everything **[DOC + audit]**

Found by auditing Phase 1 code against this design. All must be fixed before Mode 1 goes live.

> **✅ Implemented — Stage 1, step 1.** All four are done. Implementation notes are inline below. A fifth, unrelated defect surfaced during the work and is recorded as §8.6.

### 8.1 `Sale.reference` will collide across branches — **blocking**

`Sale.reference` is `unique=True`, generated from the local DB only (`SaleSerializer._next_reference()`). Two branches each independently produce `BLD-2026-0001`. In standalone that's fine — separate databases. In cloud Postgres, the second branch's push violates the unique constraint and is permanently `rejected`.

**Fix:** branch discriminator — `BLD-<branch_code>-<year>-<seq>` (e.g. `BLD-BUE-2026-0001`), with `Branch.code` assigned at enrolment. Sequence stays per-branch-per-year, so local generation still needs no coordination. Requires a migration, a change to the generator, and a receipt-template update. Existing standalone data must be backfilled with the install's own code rather than rewritten into ambiguity.

### 8.2 Outbox coverage is incomplete — **blocking**

`Product` create/edit and all `Category` writes don't write outbox entries (verified: `ProductViewSet.perform_create` and `CategoryViewSet.perform_create` omit it). Since the catalogue is exactly what must propagate HQ → branches, this is the most important gap.

### 8.3 Outbox payload has no serialization contract — **blocking**

`sync/utils._snapshot()` is documented as "deliberately dumb" — `str()` on anything non-primitive. UUIDs, dates, and FKs arrive as strings of varying shape with no versioning; the cloud can't reliably reconstruct rows. **Fix:** per-table contracts (reuse DRF serializers) plus a `schema_version` on `OutboxEntry`. Without versioning, a model change breaks every queued entry on devices mid-upgrade.

### 8.4 `HeldSale` should be excluded from sync — **decision**

Transient by design (hard-deleted on restore) and meaningful only at the till that created it. Exclude explicitly, or the hard delete produces an unmatched tombstone.

### 8.5 Branch-scoped querysets assume one branch — **non-blocking**

Every viewset filters on `request.branch_id` — correct for branches, but the HQ dashboard needs cross-branch reads. Needs a deliberate "HQ aggregate" query path gated on `is_hq` + owner role, not a relaxation of the existing filter, which is load-bearing for branch isolation.

### 8.6 `soft_delete()` discarded its own version increment — **fixed**

Found while writing tests for §8.4. `BaseModel.soft_delete()` called `save(update_fields=["deleted_at", "updated_at"])`, while `BaseModel.save()` increments `version` in memory. Because the UPDATE was restricted to the listed columns, the increment was silently dropped — every soft delete left `version` unchanged in the database.

Harmless in Phase 1 (nothing reads `version` yet), but `version` is precisely the optimistic-concurrency counter the sync engine depends on for catalogue records (feasibility §8.2), and a delete is exactly the operation you would want to detect a conflict on. Fixed by adding `"version"` to `update_fields`; regression test in `apps/core/tests/test_basemodel.py`.

This is the same class of bug as the Phase 1 close-out fix to stock writes — restricted `update_fields` silently dropping a field that `save()` had set. Worth watching for on any future `update_fields` call.

### 8.7 Implementation notes (Stage 1, step 1)

What landed, beyond what §8.1–8.4 specify:

- **`Branch.code`** — new unique field, max 8 chars. In connected mode the cloud assigns it at enrolment (§2.3); standalone installs derive it at setup via `derive_branch_code()`, which takes the first three letters of the branch name (falling back to the business name, then `"HQ"`) and appends a numeric suffix if the code is taken. Exposed on `BranchSerializer` so the frontend can identify a branch without parsing reference strings.
- **`apps/sync/registry.py`** — new module holding `SYNCED_TABLES` (table → payload schema version) and `NEVER_SYNCED` (table → reason). `write_outbox_entry()` now raises `UnregisteredTableError` for unclassified tables and returns `None` for excluded ones, so callers can invoke it unconditionally. A test asserts every `BaseModel` subclass appears in exactly one of the two dicts — adding a model without deciding its sync status now fails the suite rather than silently never replicating.
- **`serialize_instance()`** — replaces the old `str()`-everything snapshot with per-type rules: UUIDs canonical, datetimes UTC ISO-8601 with `Z`, dates ISO, `Decimal` as string, `None` preserved as null (previously `"None"`). FKs serialize from `attname` (`category_id`), so no lazy relation fetch and no nested objects.
- **Migrations** — `auth_users.0002_branch_code` (add nullable → populate → tighten to unique), `sales.0002_branch_scoped_references` (rewrites existing references; reverse refuses to run with more than one branch, since stripping codes would reintroduce ambiguity), `sync.0002_outboxentry_schema_version`.
- **Reference source** — the branch code comes from `request.user.branch.code`, not `settings.BRANCH_ID`, anticipating §2.3's move of branch identity onto the `Branch` row.

---

## 9. Build order

Sequenced so each step is independently testable and leaves the system working.

### Stage 1 — Groundwork (blocks everything)

| # | Step | Delivers | Status |
|---|---|---|---|
| 1 | Schema fixes §8.1–8.4: branch-scoped reference, outbox backfill, payload contract + `schema_version`, HeldSale exclusion | Phase 1 data becomes sync-safe | ✅ **Done** |
| 2 | Settings module core (§7) — business edit, staff management, `BusinessSettings` | Config becomes editable; gives later workstreams a home for their settings | ✅ **Done** |

Step 2 sits here deliberately: pricing bounds (B) and credit defaults (C) both need somewhere to live, and editable business config is independently valuable today.

### Stage 2 — Standalone-deliverable features

These ship without any cloud, so they reach real users fast and de-risk the schedule.

| # | Step | Delivers |
|---|---|---|
| 3 | Barcode — `Product.barcode`, USB scanner support at POS/intake (§5) | Faster till; smallest workstream — ✅ **done** |
| 4 | PIN-approval primitive — `/auth/verify-pin/` with rate limiting (§3.2) | Shared by haggling and credit — **next** |
| 5 | **Cost tracking (§7A)** — snapshot fixes, `ProductPriceHistory`, WAC on `Product`, COGS on sale lines, migration backfill | Profit becomes computable at all |
| 6 | Negotiated pricing (§3) — bounds config, POS price editing, server enforcement, variance reporting | The culturally-critical feature |
| 7 | Customer accounts & credit (§4) — models, POS integration, Customers screen, aged-debt report | Removes a real blind spot in daily cash |
| 8 | Margin & valuation reporting (§7A.6) — margin dashboard, stock valuation, margin-squeeze alerts | The owner-facing payoff of step 5 |

Step 5 lands before negotiated pricing deliberately: once cost exists, the discount floor can enforce "never below cost" (§7A.7), which is a materially stronger control than a percentage-of-catalogue floor alone.

### Stage 3 — Cloud sync & multi-branch

| # | Step | Delivers |
|---|---|---|
| 9 | `settings/branch.py`, `Branch` identity fields, enrolment + `/sync/enrol/` | Devices get cloud identities |
| 10 | Cloud `POST /sync/push/` with idempotency + per-entry results | Cloud durably receives branch writes |
| 11 | Branch push loop via `django.tasks` + `/sync/status/` | Outbox drains; one-way replication works |
| 12 | Cloud `GET /sync/pull/`; branch applies catalogue/users/config + tombstones | Two-way sync complete |
| 13 | Frontend — `SyncStatusBadge`, `useSyncStatus`, reconnection toast, sync health view | Connectivity states visible |
| 14 | HQ multi-branch dashboard — cross-branch aggregation, per-branch breakdown | The owner-facing payoff |
| 15 | Deployment — Railway Postgres, migrations, enrolment runbook | Shippable |

### Stage 4 — Optional

| # | Step | Notes |
|---|---|---|
| 16 | PO workflow (§6) | Recommend deferring — see §6.4 |
| 17 | Camera barcode scanning (§5.3) | Follow-on to USB |

**Why this order.** The original instinct was sync-first, but sequencing the standalone-deliverable features (Stage 2) ahead of the cloud gets working value to users months earlier and keeps the risky, expensive workstream from blocking everything. The one genuine cost is that credit's branch-scoping decision (§4.4) must be made *before* step 6 even though it's a sync concern — that's why it's called out as an open decision rather than deferred.

---

## 10. Open decisions

Needed before implementation starts. Roughly in order of how much they'd cost to change later.

1. **Customer credit scoping (§4.4)** — branch-scoped, shared-identity, or fully shared? Recommendation: branch-scoped. This is architectural; changing it after launch means migrating live financial data.
2. **Is HQ a branch or a console?** `HQ_BRANCH_ID = "HQ"` is currently a magic string holding catalogue products. Does HQ also sell (a real till), or is it purely management? Determines whether `is_hq` is a flag on a normal branch or a distinct deployment.
3. **Reference format (§8.1)** — is `BLD-BUE-2026-0001` acceptable on customer receipts? Customer-visible, so worth a look before it's baked in.
4. **Cost backfill for existing products (§7A.8)** — products with no purchase history have no derivable cost. Confirm the approach: flag them as "cost not set" and exclude from margin reporting, rather than defaulting to 0 and reporting a false 100% margin.
5. **Should the discount floor enforce "never below cost" (§7A.7)?** — recommended once cost exists, but it means a cashier cannot clear slow-moving stock at a loss without manager approval. That may be exactly what you want, or an obstruction.
6. **Is the PO workflow wanted at all (§6.4)?** — or deferred to Phase 3 in favour of credit and barcode?
5. **Existing standalone installs** — any real deployments with data that must migrate into a connected setup, or is Phase 2 greenfield? Affects migration care in §8.1.
6. **Enrolment trust model (§2.3)** — one-time codes (friendlier) or pre-shared credentials (simpler to build)?
7. **Cloud hosting timing** — provision Railway early (steps 8+ are hard to test without a real remote), or stay local-Docker until step 13?

---

## 11. Out of scope (Phase 3+)

Per feasibility §11, unchanged: Tauri desktop wrapper, thermal ESC/POS printing, real MoMo API integration, HR & payroll, OHADA accounting, French localisation. Also deferred: the cashier surplus-incentive scheme (feasibility §10.3 explicitly flags it as *not* a Phase 2 requirement).
