# Bledger Phase 2 — Cloud Sync & Multi-Branch

**Status:** design proposal, pending review
**Scope of this document:** cloud sync + multi-branch only. Negotiated pricing, customer credit, barcode scanning, and the settings module are also Phase 2 in the feasibility doc but are separate workstreams and are not designed here.

---

## 1. What we're building

Phase 1 shipped **Mode 2 (Standalone)**: one shop, one device, SQLite, no internet. Phase 2 adds **Mode 1 (Connected)**: several branches, each still running fully offline on its own SQLite, with a central PostgreSQL cloud that aggregates everything and lets the owner see the whole business.

The governing principle, unchanged from the feasibility doc §8.1:

> No user action ever waits on the cloud. Every write goes to local SQLite first, the outbox queue second, and the cloud third.

A branch that loses internet for a week keeps selling normally. The outbox accumulates and drains on reconnect. This is not a "sync feature" bolted onto an online app — it's an offline app that happens to replicate.

### What makes this tractable

Per feasibility doc §6, **branches never share editable records**. No two branches can modify the same row, so there is no general merge problem. There is exactly one shared layer — the HQ product catalogue, pushed down read-only. That reduces "distributed conflict resolution" (hard) to "one-way catalogue propagation plus append-only replication" (manageable).

---

## 2. Architecture

Decision (this session): **sync lives inside the existing Django project**, not a separate FastAPI service as feasibility doc §7 suggested. One codebase, one deploy, reuses the existing models, auth, and permission classes. SME branch sync volume is a few hundred rows a day — async throughput is not the constraint. Extract later if that stops being true.

```
Branch device (Mode 1)                        Cloud (Railway / DigitalOcean)
┌────────────────────────────┐                ┌──────────────────────────────┐
│ Django + SQLite            │                │ Django + PostgreSQL          │
│  • POS, inventory, etc.    │                │  • same codebase,            │
│  • writes → local DB       │  push (30s)    │    DJANGO_SETTINGS_MODULE=   │
│  • writes → OutboxEntry    │ ─────────────► │    bledger.settings.connected│
│    (same transaction)      │                │  • source of truth across    │
│  • sync engine drains      │  pull (30s)    │    branches                  │
│    outbox                  │ ◄───────────── │  • HQ dashboard reads here   │
└────────────────────────────┘                └──────────────────────────────┘
        ▲                                                    ▲
        │ same code, SYNC_ENABLED=False                      │
   Mode 2 standalone install                          Owner's browser (HQ)
```

The same Django codebase runs in both roles. `settings/connected.py` (already written) configures the cloud side; branch devices run a new `settings/branch.py`. What differs is which sync role the process plays, not what code it contains.

### 2.1 The third settings module

Today: `standalone.py` (SQLite, sync off) and `connected.py` (Postgres, sync on). But `connected.py` currently describes *the cloud*, while a branch device in Mode 1 is a third thing: SQLite locally **and** sync on.

Proposed: add `settings/branch.py` — SQLite, `SYNC_ENABLED=True`, plus `CLOUD_API_URL` / branch credentials. `connected.py` keeps its current meaning (the cloud server). Standalone is untouched.

| Module | DB | SYNC_ENABLED | Role |
|---|---|---|---|
| `standalone.py` | SQLite | False | Phase 1 single-shop install (unchanged) |
| `branch.py` *(new)* | SQLite | True | Mode 1 branch device — pushes/pulls to cloud |
| `connected.py` | PostgreSQL | True | The cloud server — receives pushes, serves pulls |

---

## 3. Branch identity and enrolment

**This is the biggest gap in the current code.** Today `BRANCH_ID` is a static string in `.env` (`default="HQ"`), stamped onto every request by `DeploymentContextMiddleware`. That works for one install. For multi-branch it's unworkable: a branch needs a real, cloud-issued identity plus credentials to authenticate its pushes, and nothing stops two installs claiming the same `BRANCH_ID`.

### Proposed enrolment flow

1. Owner, in the HQ dashboard, creates a branch record (name, area) → cloud returns a one-time **enrolment code** (short, human-typeable, expiring).
2. On the new branch device, the setup wizard gains a "Connect to head office" path. The manager enters the enrolment code.
3. Device POSTs the code to `/api/v1/sync/enrol/`. Cloud validates it, marks it consumed, and returns: the canonical `branch_id` (UUID), a long-lived **device sync token**, and the branch's config.
4. Device persists these locally. `BRANCH_ID` stops being an env constant and becomes a value read from the local `Branch` row.

This gives every branch a cloud-issued identity, revocable credentials (owner can deactivate a lost/stolen device), and no possibility of two branches colliding on ID.

### Required model changes

- `Branch` gains: `is_hq` (bool), `cloud_id` (UUID, the canonical cloud identity), `sync_token` (write-only), `last_synced_at`, `is_active`.
- New `EnrolmentCode` model, cloud-side only: `code`, `branch`, `expires_at`, `consumed_at`.
- `DeploymentContextMiddleware` reads `branch_id` from the local `Branch` row, falling back to `settings.BRANCH_ID` so standalone installs are unaffected.

---

## 4. The sync protocol

Two endpoints, both cloud-side, both authenticated by the device sync token (not a user token — sync is a device-level operation and must work with no user logged in).

### 4.1 `POST /api/v1/sync/push/`

Branch → cloud. Body is a batch of outbox entries:

```json
{
  "branch_id": "…uuid…",
  "entries": [
    {
      "outbox_id": "…uuid…",
      "table_name": "sales_sale",
      "record_id": "…uuid…",
      "operation": "insert",
      "payload": { "...": "..." },
      "created_at": "2026-07-21T14:03:11Z"
    }
  ]
}
```

Response reports per-entry outcome so a poison row can never block the queue:

```json
{
  "results": [
    { "outbox_id": "…", "status": "applied" },
    { "outbox_id": "…", "status": "duplicate" },
    { "outbox_id": "…", "status": "rejected", "error": "unknown product 9f2…" }
  ],
  "server_time": "2026-07-21T14:03:12Z"
}
```

**Idempotency is mandatory.** A branch that pushes successfully but loses the response before recording it will push again. The cloud must treat a re-pushed `outbox_id` as `duplicate` and no-op. Implementation: unique index on `(branch_id, outbox_id)` in a cloud-side `AppliedEntry` table, checked inside the same transaction that applies the write.

Entry outcomes:

| Status | Meaning | Branch does |
|---|---|---|
| `applied` | Written to cloud | Set `synced_at`, stop retrying |
| `duplicate` | Already applied earlier | Same as `applied` |
| `rejected` | Permanently invalid (bad FK, schema mismatch) | Record `last_error`, stop retrying, surface to owner |
| *(HTTP 5xx / timeout)* | Transient | Increment `attempted`, retry with backoff |

The `rejected` vs. retry distinction matters: without it, one malformed row retries forever and the queue never drains.

### 4.2 `GET /api/v1/sync/pull/?since=<timestamp>`

Cloud → branch. Returns records this branch needs that changed after `since`:

- **HQ catalogue** — `Product` and `Category` rows owned by HQ. Read-only at the branch.
- **Tombstones** — soft-deleted catalogue rows (`deleted_at` set), so deletions propagate.
- **User accounts** — `BledgerUser` rows for this branch (owner manages staff centrally per feasibility doc §6).
- **Branch config changes** — renames, receipt footer edits made at HQ.

A branch never pulls another branch's sales or stock. Aggregation is the HQ dashboard's job, reading cloud Postgres directly — not something branches replicate.

Response is paginated with a cursor, and `since` uses the **server's** clock (returned as `server_time` on every response and stored locally), never the device's. Branch device clocks in the field are not trustworthy; anchoring on server time avoids missed or repeated windows.

---

## 5. Conflict rules

Per feasibility doc §6 there is no cross-branch conflict. The rules needed are narrower:

| Situation | Rule | Rationale |
|---|---|---|
| Branch pushes a sale/purchase/adjustment | **Always accept** (append-only) | Branch owns its own transactional records outright. These are facts that already happened at the till. |
| HQ edits a catalogue product while a branch has an unpushed local edit | **HQ wins** | Catalogue is HQ-owned; branches were never permitted to edit it. Only `BranchPriceOverride` is branch-editable, and it's a separate row. |
| Two branches both set a price override | **No conflict** | Unique per `(product, branch)` — separate rows by construction. |
| Same record pushed twice | **Idempotent no-op** | See §4.1. |
| Stock levels | **Never synced as absolute values** | See below. |

### Stock is a derived quantity, not a synced field

`Product.stock_level` must **not** be replicated as an absolute number. Two branches pushing "stock_level = 40" is meaningless — they hold different physical stock, and HQ's aggregate is a sum, not a winner.

Instead: stock movements (`StockAdjustment`, sale line items, purchase line items) sync as the append-only events they already are, and any aggregate stock figure at HQ is **computed from those events per branch**. This matches the feasibility doc's glossary definition of delta sync ("syncing changes rather than absolute values, so changes always combine correctly").

Practically, this means the cloud stores per-branch stock as a projection over synced movements rather than trusting a pushed `stock_level` column. The local `stock_level` field stays exactly as it is for the branch's own fast reads.

---

## 6. Blocking issues in the current schema

Found while auditing Phase 1 code against this design. All must be fixed before sync goes live.

### 6.1 `Sale.reference` will collide across branches — **blocking**

`Sale.reference` is `unique=True`, and `SaleSerializer._next_reference()` computes the next value from the local database only. Two branches will each independently generate `BLD-2026-0001`. In standalone that's fine — separate databases. In the cloud Postgres, the second branch's push violates the unique constraint and is permanently `rejected`.

**Fix:** include a branch discriminator: `BLD-<branch_code>-<year>-<seq>` (e.g. `BLD-BUE-2026-0001`), with a short `Branch.code` assigned at enrolment. Sequence stays per-branch-per-year, so branch-local generation still needs no coordination. Requires a migration and a change to the reference generator and receipt template.

Note this affects existing standalone installs' historical data — migration must backfill old references with the install's own branch code rather than rewriting them into ambiguity.

### 6.2 Outbox coverage is incomplete — **blocking**

Carried over from the Phase 1 close-out. `Product` create/edit and all `Category` writes don't write outbox entries. Since the catalogue is exactly the data that must propagate HQ → branches, this is the single most important gap. Fix in `ProductViewSet.perform_create/perform_update` and `CategoryViewSet`.

### 6.3 The outbox payload has no real serialization contract — **blocking**

`sync/utils._snapshot()` is documented as "deliberately dumb": `str()` on anything non-primitive. That means UUIDs, dates, and FKs all arrive as strings of varying shape, and there's no versioning. The cloud can't reliably reconstruct a row from it.

**Fix:** define a per-table serialization contract — reuse the existing DRF serializers where possible — and add a `schema_version` integer to `OutboxEntry`. Without versioning, a future model change breaks every queued entry on older devices mid-upgrade.

### 6.4 `HeldSale` should be excluded from sync — **decision**

`HeldSale` is transient (hard-deleted on restore, by design). Held carts are meaningful only at the till that created them. Recommend explicitly excluding it from sync rather than leaving it ambiguous — otherwise the hard delete produces an unmatched tombstone.

### 6.5 Branch-scoped querysets assume a single branch — **non-blocking**

Every viewset filters on `request.branch_id`. Correct for branches, but the HQ dashboard needs cross-branch reads. Needs a deliberate "HQ aggregate" query path gated on `is_hq` + owner role — not a relaxation of the existing filter, which is load-bearing for branch isolation.

---

## 7. Connectivity UX

The four states from feasibility doc §5 need real UI. The topbar already has a hardcoded "● Synced" indicator (`screen-sync-dot`) — Phase 2 makes it real.

| State | Indicator | Detail |
|---|---|---|
| Fully online | Green ● Synced | Last sync time on hover |
| Degraded | Amber ● Syncing… | Pending-changes count |
| Fully offline | Red ● Offline | "Last synced 2h ago" |
| Reconnection | Toast: "X changes synced" | Catalogue updates applied |

Implementation: a `useSyncStatus` hook polling a local `GET /api/v1/sync/status/` (pending count, last success, last error), plus a `SyncStatusBadge` component replacing the hardcoded dot. The badge must never block interaction — offline is a normal working state, not an error.

An owner-facing sync health view (pending entries, rejected entries with reasons, per-branch last-seen) is needed too. Rejected entries are silent data loss unless someone can see them.

---

## 8. Background execution

Use Django 6.0's native `django.tasks` (already the locked decision, superseding the feasibility doc's Django-Q2/Celery plan). A periodic task per branch device:

1. Drain outbox → `POST /sync/push/` in batches (suggest 100 entries).
2. `GET /sync/pull/?since=<last_server_time>` → apply catalogue/user/config changes.
3. Record results, update `last_synced_at`.

Cadence 30s when online (feasibility doc §5), exponential backoff to a ceiling of ~15 min when failing, immediate flush on reconnect detection. Must hold a lock so two overlapping runs can't double-push.

---

## 9. Proposed build order

Each step is independently testable and leaves the system working.

| # | Step | Delivers |
|---|---|---|
| 1 | Schema fixes: branch-scoped `Sale.reference`, outbox backfill (Product/Category), payload contract + `schema_version` | Phase 1 data becomes sync-safe. No new features — pure groundwork. |
| 2 | `settings/branch.py`, `Branch` identity fields, enrolment models + `/sync/enrol/` | A device can be enrolled to a cloud and get an identity. |
| 3 | Cloud: `POST /sync/push/` with idempotency + per-entry results | Cloud can receive and durably apply branch writes. |
| 4 | Branch: sync engine push loop via `django.tasks` + `/sync/status/` | Outbox actually drains. End-to-end one-way replication works. |
| 5 | Cloud: `GET /sync/pull/`; branch: apply catalogue/user/config + tombstones | HQ catalogue propagates down. Two-way sync complete. |
| 6 | Frontend: `SyncStatusBadge`, `useSyncStatus`, reconnection toast, sync health view | The four connectivity states are visible to users. |
| 7 | HQ multi-branch dashboard: cross-branch aggregation, per-branch breakdown | The owner-facing payoff. |
| 8 | Deployment: Railway Postgres, migrations, enrolment runbook | Actually shippable. |

Steps 1–2 are the ones worth doing carefully; they're schema-level and expensive to change later. Steps 3–5 are the core engine. Step 7 is where the feature becomes visible to the customer.

---

## 10. Open decisions

These need your call before implementation starts:

1. **Is HQ a branch or a separate thing?** Today `HQ_BRANCH_ID = "HQ"` is a magic string and HQ-catalogue products live under it. Does HQ also sell (i.e. is it a real till), or is it purely a management console? Changes whether `is_hq` is a flag on a normal branch or a distinct deployment.
2. **Reference format.** Is `BLD-BUE-2026-0001` acceptable on receipts, or do you want the branch code elsewhere? This is customer-visible.
3. **Existing standalone installs.** Do any real installs have data that must migrate into a connected deployment, or is Phase 2 greenfield? Affects how much migration care §6.1 needs.
4. **Enrolment trust model.** One-time codes as proposed, or pre-shared credentials generated at HQ and typed in? Codes are friendlier; pre-shared is simpler to build.
5. **Cloud hosting now or later?** Railway per the doc. Worth provisioning early (step 3 onward is hard to test without a real remote) or keep it local-Docker until step 8?

---

## 11. Explicitly out of scope here

Also Phase 2 per the feasibility doc, but separate workstreams needing their own design: negotiated pricing / haggling UI (data model already in place), customer accounts & credit, barcode scanning, PO workflow & supplier payments, full settings module.
