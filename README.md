# Bledger — Business Ledger

Business management system for Cameroonian SMEs (retail shops, boutiques,
provision stores). See `Bledger_Design_v0.5.docx` and
`Bledger_Feasibility_Design_v0.3.docx` for full product/technical design.

## Modes

- **Standalone** (Phase 1 target) — SQLite only, no internet required.
  `DJANGO_SETTINGS_MODULE=bledger.settings.standalone`
- **Connected** (Phase 2) — PostgreSQL + outbox sync engine.
  `DJANGO_SETTINGS_MODULE=bledger.settings.connected`

## Quick start (standalone / local dev)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp ../.env.example ../.env
export DJANGO_SETTINGS_MODULE=bledger.settings.development
python manage.py migrate
python manage.py runserver
```

React frontend lives in `frontend/` (not yet scaffolded) and proxies
`/api/*` to this Django server during development.

## Project layout

```
backend/
  manage.py
  bledger/                 Django project package
    settings/               base / development / standalone / connected / production / testing
    urls.py                 mounts all app routes under /api/v1/
  apps/
    core/                   BaseModel, shared permissions, pagination, XAF helpers
    auth_users/              (Phase 1, next)
    inventory/                "
    sales/                     "
    printing/                   "
    suppliers/                   "
    dashboard/                    "
    sync/                   Phase 2, scaffolded but disabled
```

This commit scaffolds **only** the project skeleton and the `core` app —
no business-logic apps yet, per the agreed build order in
`Bledger_Design_v0.5.docx` (Part C / Next Steps).
