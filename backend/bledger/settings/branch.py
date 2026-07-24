"""
Mode 1 — Branch device (Phase 2 design §2.2, "third settings module").

A branch device is a third deployment shape the existing two modules don't
cover: it runs SQLite locally like standalone, but has sync switched on
like the cloud. connected.py describes *the cloud server* (PostgreSQL,
source of truth); this describes a *branch till* that operates fully
offline on its own SQLite yet replicates to head office when it can.

| Module        | DB         | SYNC_ENABLED | Role                       |
|---------------|------------|--------------|----------------------------|
| standalone.py | SQLite     | False        | Phase 1 single-shop install|
| branch.py     | SQLite     | True         | Mode 1 branch device (this)|
| connected.py  | PostgreSQL | True         | The cloud server           |

The device's own identity (branch_id) and sync_token are NOT set here — a
branch reads them from its local Branch row after enrolment (§2.3), so
BRANCH_ID stays at its harmless env default until the device enrols.
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

# Sync is on, but staff still authenticate locally (PIN / username) exactly
# as in standalone — CLOUD_AUTH is about the cloud *server's* user store,
# which a branch till doesn't use. The device authenticates to the cloud
# with its device sync token, not a user login.
SYNC_ENABLED = True
CLOUD_AUTH_ENABLED = False

# Base URL of the head-office cloud this device enrols with and pushes /
# pulls against (§2.4). Empty until the device is pointed at an HQ.
CLOUD_API_BASE_URL = env("CLOUD_API_BASE_URL", default="")

# Outbox sync cadence (seconds) — 30s online, per §2.7. The backoff loop
# itself is step 11.
SYNC_PUSH_INTERVAL_SECONDS = env.int("SYNC_PUSH_INTERVAL_SECONDS", default=30)

# One-time enrolment codes are minted on the cloud, never on a branch, so
# this window is really a cloud concern; kept here only so the setting
# resolves uniformly across modules.
ENROLMENT_CODE_TTL_DAYS = env.int("ENROLMENT_CODE_TTL_DAYS", default=7)

# Same LAN-only CORS posture as standalone: other devices in the shop point
# their browser at this host's local IP (design doc §4.2).
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(192\.168|10)\.\d+\.\d+\.\d+(:\d+)?$"]

# django.tasks backend for the sync push loop (Phase 2 design §2.7). The
# immediate backend runs an enqueued task inline and needs no extra tables;
# it's a safe default because the *tested* trigger is `manage.py sync_push`
# from system cron, not a background worker. Swap in a durable backend
# (e.g. django.tasks database backend) if you'd rather run a worker.
TASKS = {
    "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
}
