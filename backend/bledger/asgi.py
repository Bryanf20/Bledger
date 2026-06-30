"""
ASGI config. Not used for serving in Phase 1 (gunicorn/WSGI is the
production path), but kept ready for WebSocket support (e.g. live
multi-branch dashboard updates) in Phase 2.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bledger.settings.production")

application = get_asgi_application()
