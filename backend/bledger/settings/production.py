"""
Production deploy target. Inherits `connected` (Mode 1 is the only mode
that runs as a hosted service — standalone installs don't use this
module at all, they ship `standalone.py` inside the Tauri bundle).

Adds: security headers, static file serving via whitenoise, Sentry.
"""
from .connected import *  # noqa: F401,F403
from .connected import MIDDLEWARE, env

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

MIDDLEWARE = MIDDLEWARE[:1] + ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE[1:]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
