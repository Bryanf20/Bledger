"""
Local development. Inherits base — SQLite DB, debug toolbar, CORS open
to the React dev server. This is what you run day-to-day while building;
`standalone.py` is the equivalent settings module baked into a packaged
release.
"""
from .base import *
from .base import BASE_DIR, INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / env("SQLITE_PATH", default="db.sqlite3"),
    }
}

SYNC_ENABLED = False

INSTALLED_APPS = INSTALLED_APPS + ["debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
INTERNAL_IPS = ["127.0.0.1"]

# React dev server (Vite) runs separately and proxies /api/* here.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
