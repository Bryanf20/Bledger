"""
Mode 1 — Connected (cloud-backed). Inherits base.

- PostgreSQL as the central cloud database (source of truth across
  branches). SQLite still runs at each branch device as the operational
  DB — this module only configures the *cloud* side.
- SYNC_ENABLED = True — the outbox sync engine (apps.sync) is active.
- Railway for MVP hosting, DigitalOcean at scale (see design doc
  Section 7 / Section 12 Phase 2).

NOTE: the design doc's Section 7 background-task plan (Django-Q2 ->
Celery + Redis) predates the decision to build on Django 6.0. Since
6.0 ships a native `django.tasks` framework, prefer that for the
Phase 2 sync loop over adding Celery/Redis as a dependency — it
covers task definition/queuing out of the box; only reach for an
external broker if django.tasks' built-in backends prove insufficient
at scale.
"""
from .base import *
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=False)

# Railway (and most PaaS) inject a single DATABASE_URL for the provisioned
# Postgres plugin; prefer it when present, and fall back to the discrete
# POSTGRES_* vars for local docker-compose / DigitalOcean setups. Either way
# this is the *cloud* database — branch devices stay on SQLite.
if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"].setdefault("CONN_MAX_AGE", 600)
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": 600,
        }
    }

SYNC_ENABLED = True
CLOUD_AUTH_ENABLED = True

# Outbox sync cadence (seconds) — see design doc Section 5, "Fully
# online" pushes outbox every 30s.
SYNC_PUSH_INTERVAL_SECONDS = env.int("SYNC_PUSH_INTERVAL_SECONDS", default=30)

CORS_ALLOWED_ORIGINS = env.list("DJANGO_CORS_ALLOWED_ORIGINS", default=[])

# django.tasks backend for the sync push loop (Phase 2 design §2.7). The
# immediate backend runs an enqueued task inline and needs no extra tables;
# it's a safe default because the *tested* trigger is `manage.py sync_push`
# from system cron, not a background worker. Swap in a durable backend
# (e.g. django.tasks database backend) if you'd rather run a worker.
TASKS = {
    "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
}
