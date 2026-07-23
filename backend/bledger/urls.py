"""
Root URL configuration.

Each app owns its own urls.py and is mounted here under /api/v1/.
"""
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.auth_users.urls import (
    auth_urlpatterns,
    settings_urlpatterns,
    setup_urlpatterns,
    user_urlpatterns,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include(auth_urlpatterns)),
    path("api/v1/setup/", include(setup_urlpatterns)),
    path("api/v1/users/", include(user_urlpatterns)),
    path("api/v1/settings/", include(settings_urlpatterns)),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.sales.urls")),
    path("api/v1/", include("apps.suppliers.urls")),
    path("api/v1/", include("apps.customers.urls")),
    path("api/v1/", include("apps.finances.urls")),
    path("api/v1/", include("apps.activity.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
    # path("api/v1/sync/", include("apps.sync.urls")),  # Phase 2, 503 until enabled
]

if settings.DEBUG and apps.is_installed("debug_toolbar"):
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
