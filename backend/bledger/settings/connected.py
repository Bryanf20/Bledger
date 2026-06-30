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
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=False)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

SYNC_ENABLED = True
CLOUD_AUTH_ENABLED = True

# Outbox sync cadence (seconds) — see design doc Section 5, "Fully
# online" pushes outbox every 30s.
SYNC_PUSH_INTERVAL_SECONDS = env.int("SYNC_PUSH_INTERVAL_SECONDS", default=30)

CORS_ALLOWED_ORIGINS = env.list("DJANGO_CORS_ALLOWED_ORIGINS", default=[])
