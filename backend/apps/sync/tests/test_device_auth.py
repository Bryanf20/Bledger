"""
DeviceSyncTokenAuthentication (Phase 2 design §2.4) — resolves a device's
sync token to its Branch, with no user logged in.
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from apps.auth_users.models import Branch
from apps.sync.authentication import DeviceSyncTokenAuthentication


def _authenticate(header=None):
    kwargs = {"HTTP_AUTHORIZATION": header} if header is not None else {}
    request = APIRequestFactory().get("/api/v1/sync/status/", **kwargs)
    return DeviceSyncTokenAuthentication().authenticate(request)


@pytest.mark.django_db
def test_valid_token_resolves_to_branch(new_branch):
    Branch.objects.filter(pk=new_branch.pk).update(sync_token="tok-abc")
    user, branch = _authenticate("SyncToken tok-abc")
    assert isinstance(user, AnonymousUser)
    assert branch.pk == new_branch.pk


def test_no_authorization_header_defers(db):
    assert _authenticate(None) is None


@pytest.mark.django_db
def test_non_synctoken_scheme_defers(new_branch):
    # A normal user Token request must fall through to other authenticators.
    assert _authenticate("Token whatever") is None


@pytest.mark.django_db
def test_unknown_token_is_rejected(db):
    with pytest.raises(AuthenticationFailed):
        _authenticate("SyncToken does-not-exist")


@pytest.mark.django_db
def test_deactivated_branch_token_is_rejected(new_branch):
    Branch.objects.filter(pk=new_branch.pk).update(
        sync_token="tok-abc", is_active=False
    )
    with pytest.raises(AuthenticationFailed):
        _authenticate("SyncToken tok-abc")


def test_malformed_header_missing_credentials(db):
    with pytest.raises(AuthenticationFailed):
        _authenticate("SyncToken")


def test_malformed_header_extra_spaces(db):
    with pytest.raises(AuthenticationFailed):
        _authenticate("SyncToken a b")
