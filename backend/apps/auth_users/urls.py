"""
URL patterns for this app are split into four lists because they mount
under four different prefixes in the root URLconf (design doc Part E.1
and E.6 list these as separate route groups, not all under /auth/):

    /api/v1/auth/...      -> auth_urlpatterns
    /api/v1/setup/...     -> setup_urlpatterns
    /api/v1/users/...     -> user_urlpatterns
    /api/v1/settings/...  -> settings_urlpatterns   (Phase 2 §7)

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
    path("templates/", views.ProductTemplateListView.as_view(), name="setup-templates"),
    path("load-template/", views.LoadTemplateView.as_view(), name="setup-load-template"),
    path("", views.SetupView.as_view(), name="setup"),
]

user_urlpatterns = [
    path("", views.StaffUserListCreateView.as_view(), name="users"),
    path("<uuid:pk>/", views.StaffUserDetailView.as_view(), name="user-detail"),
    path("<uuid:pk>/reset-pin/", views.StaffUserResetPinView.as_view(), name="user-reset-pin"),
]

settings_urlpatterns = [
    path("business/", views.SettingsBusinessView.as_view(), name="settings-business"),
    path("preferences/", views.BusinessSettingsView.as_view(), name="settings-preferences"),
]
