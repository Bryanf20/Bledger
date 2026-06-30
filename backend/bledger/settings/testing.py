"""
Test runner settings. Inherits base — in-memory SQLite, fast password
hasher, sync disabled. Used by pytest-django via DJANGO_SETTINGS_MODULE
in pytest.ini / pyproject.toml.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SYNC_ENABLED = False
CLOUD_AUTH_ENABLED = False

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

LOGGING_CONFIG = None  # quiet test output
