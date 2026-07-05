"""
Root URL configuration.

Each app owns its own urls.py and is mounted here under /api/v1/.
Business-logic apps (auth_users, inventory, sales, suppliers, dashboard,
sync) are not scaffolded yet — they'll add their own include() lines as
they're built, in the order described in Bledger_Design_v0.5.docx Part C.
"""
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.auth_users.urls import auth_urlpatterns, setup_urlpatterns, user_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include(auth_urlpatterns)),
    path("api/v1/setup/", include(setup_urlpatterns)),
    path("api/v1/users/", include(user_urlpatterns)),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.sales.urls")),
    # path("api/v1/", include("apps.suppliers.urls")),
    # path("api/v1/dashboard/", include("apps.dashboard.urls")),
    # path("api/v1/sync/", include("apps.sync.urls")),  # Phase 2, 503 until enabled
]

if settings.DEBUG and apps.is_installed("debug_toolbar"):
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
