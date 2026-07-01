"""
URL patterns for this app are split into three lists because they mount
under three different prefixes in the root URLconf (design doc Part E.1
and E.6 list these as separate route groups, not all under /auth/):

    /api/v1/auth/...    -> auth_urlpatterns
    /api/v1/setup/...   -> setup_urlpatterns
    /api/v1/users/...   -> user_urlpatterns

See bledger/urls.py for how each is included.
"""
from django.urls import path

from . import views

auth_urlpatterns = [
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("pin-login/", views.PinLoginView.as_view(), name="auth-pin-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
]

setup_urlpatterns = [
    path("status/", views.SetupStatusView.as_view(), name="setup-status"),
    path("load-template/", views.LoadTemplateView.as_view(), name="setup-load-template"),
    path("", views.SetupView.as_view(), name="setup"),
]

user_urlpatterns = [
    path("", views.StaffUserCreateView.as_view(), name="users"),
]
