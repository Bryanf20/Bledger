# Bledger — Cloud Deployment & Branch Enrolment (Phase 2, Stage 3, step 15)

This covers standing up the **head-office cloud** (the central PostgreSQL +
Django service that aggregates all branches) and **enrolling branch devices**
into it. It is the operational counterpart to the sync engine built in steps
9–14.

## Mental model — what runs where

| Piece | Deployment | DB | Settings module |
|---|---|---|---|
| **Head office / cloud** | Hosted (Railway) | PostgreSQL | `bledger.settings.production` |
| **Branch device** | On-site machine at the shop | SQLite | `bledger.settings.branch` |
| **Standalone install** (Phase 1) | On-site, offline | SQLite | `bledger.settings.standalone` |

Only the **cloud** is deployed to Railway. Branch devices run locally and
reach the cloud over the internet; they keep working offline and sync when
they can. The cloud is a *receiver* of pushes and *server* of catalogue
pulls — it does not run the sync loop itself.

---

## Part A — Deploy the cloud to Railway

### A1. Prerequisites
- A Railway account and project.
- This repo connected to Railway (GitHub deploy or `railway up`).

### A2. Provision PostgreSQL
Add the **PostgreSQL** plugin to the Railway project. Railway injects
`DATABASE_URL` into the service automatically; `settings/connected.py` prefers
it over the discrete `POSTGRES_*` vars.

### A3. Point Railway at the backend
The Django app lives in `backend/`. Set the service **Root Directory** to
`backend`. `backend/railway.json` then drives build and deploy:
- **build:** `pip install -r requirements/prod.txt && manage.py collectstatic`
- **preDeploy:** `manage.py migrate --no-input`
- **start:** `gunicorn bledger.wsgi:application --bind 0.0.0.0:$PORT --workers 3`
- **healthcheck:** `/api/v1/health/`

### A4. Environment variables
Set these on the Railway service:

```
DJANGO_SETTINGS_MODULE=bledger.settings.production
DJANGO_SECRET_KEY=<a long random secret>
DEPLOYMENT_MODE=connected
BRANCH_ID=HQ
DJANGO_ALLOWED_HOSTS=<your-app>.up.railway.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-app>.up.railway.app
DJANGO_CORS_ALLOWED_ORIGINS=https://<your-app>.up.railway.app
# DATABASE_URL is injected by the Postgres plugin
# SENTRY_DSN=<optional>
```

`production.py` sets `SECURE_SSL_REDIRECT`, HSTS, WhiteNoise static serving,
and `SECURE_PROXY_SSL_HEADER` (Railway terminates TLS at its edge — this
prevents a redirect loop).

### A5. First deploy
Trigger a deploy. The release/preDeploy step runs migrations, so all Phase
1 + Phase 2 tables (including `sync_enrolmentcode`, `sync_appliedentry`,
`sync_syncstate`) are created. Confirm:

```
curl https://<your-app>.up.railway.app/api/v1/health/
```

### A6. Create the head-office branch + owner
Run once (Railway shell, or `railway run`):

```
python manage.py createsuperuser        # optional Django admin
# Create the HQ Branch + owner account via the setup wizard API, or shell:
python manage.py shell -c "
from apps.auth_users.models import Branch, BledgerUser
b = Branch.objects.create(business_name='Tabi Provisions', branch_name='Head Office', code='HQ', is_hq=True, deployment_mode='connected', setup_complete=True)
BledgerUser.objects.create_user(username='owner', branch=b, role='owner', password='<set a strong password>', name='Owner')
print('HQ branch', b.id)
"
```

> Marking HQ with `is_hq=True` makes the HQ dashboard attribute HQ's own
> sales correctly (see the identity-reconciliation note in step 14). If you
> used the setup wizard instead (which defaults `is_hq=False`), set it after:
> `Branch.objects.filter(code='HQ').update(is_hq=True)`.

---

## Part B — Enrol a branch device

Each branch runs its own copy of Bledger in **branch** mode. Enrolment gives
that device a cloud identity + sync token (Phase 2 §2.3).

### B1. On the CLOUD — provision the branch, get a code
```
python manage.py provision_branch --branch-name "Limbe Branch" --code LMB
```
Prints a one-time **enrolment code** (default validity 7 days) and the
command to run on the device. This is the CLI equivalent of the owner-only
`POST /api/v1/sync/branches/` endpoint (the operable path until the HQ
branch-management screen ships).

### B2. On the DEVICE — configure branch mode
Install Bledger on the branch machine and set:
```
DJANGO_SETTINGS_MODULE=bledger.settings.branch
CLOUD_API_BASE_URL=https://<your-app>.up.railway.app
SQLITE_PATH=db.sqlite3
```
Run migrations: `python manage.py migrate`.

### B3. On the DEVICE — redeem the code
```
python manage.py enrol_device --code <CODE_FROM_B1>
```
This calls `/api/v1/sync/enrol/`, consumes the code, and writes the returned
`branch_id` (as `cloud_id`), device `sync_token`, and branch config into the
device's local `Branch` row. From here `DeploymentContextMiddleware` stamps
the cloud-assigned `branch_id` on every record.

### B4. On the DEVICE — schedule the sync loop
Point cron at the combined push+pull cycle (safe to run frequently — it
self-limits via the run lock and backoff):
```
* * * * *  cd /path/to/backend && python manage.py sync
```
(For sub-minute cadence, run a small loop that calls `manage.py sync` every
~30s.) Watch health with `GET /api/v1/sync/status/`, or the in-app sync badge
and the owner **Sync health** screen.

---

## Part C — Verify end-to-end
1. On the device, record a sale. `/sync/status/` shows `pending: 1`.
2. After a sync cycle it shows `pending: 0`, `connectivity: synced`, and the
   reconnection toast fires.
3. On the cloud, the owner's **HQ** dashboard shows the branch with its
   revenue and a fresh "last synced" time.
4. Edit the catalogue at HQ; on the next device pull the change (and any
   discontinued-product tombstones) appears in the branch's inventory.

## Notes / rollback
- **Migrations** run in the preDeploy step; a failed migration fails the
  deploy before traffic shifts. To roll back, redeploy the previous commit.
- Rejected pushes are visible to the owner on the **Sync health** screen
  (`rejected_at` + reason) — they never silently vanish.
- Branch devices are resilient to cloud downtime: they queue in the outbox
  and drain on reconnect.

## Known follow-ups (tracked in project notes)
- HQ branch-management UI (provisioning is CLI/API today).
- Branch `BledgerUser` + business-config pull (catalogue pull is done).
- Verify the `django.tasks` worker path on real Django 6.0 (cron path is the
  tested one).
- Run the frontend `npm run build` locally (couldn't run in the build sandbox).
