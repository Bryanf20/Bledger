"""
Mode 2 — Standalone (fully local). Inherits base.

- SQLite only, no PostgreSQL, no cloud dependency whatsoever.
- SYNC_ENABLED = False — the sync app's outbox table still exists (created
  in Phase 1 migrations) but the engine never runs.
- No cloud auth — login is local-only (PIN for cashier, username/password
  for owner/manager).

This is the settings module baked into the Tauri-wrapped desktop build
(Phase 3) and used for any business with no internet access today.
"""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = env.bool("DJANGO_DEBUG", default=False)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / env("SQLITE_PATH", default="db.sqlite3"),
    }
}

SYNC_ENABLED = False
CLOUD_AUTH_ENABLED = False

# Standalone installs serve one branch from one device; other devices on
# the same LAN point their browser at this host's local IP (see design
# doc Section 4.2). No CORS allow-list needed beyond same-origin/LAN.
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(192\.168|10)\.\d+\.\d+\.\d+(:\d+)?$"]
