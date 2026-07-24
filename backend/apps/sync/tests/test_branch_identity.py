"""
Branch cloud-identity fields and helpers (Phase 2 design §2.3), plus the
DeploymentContextMiddleware branch_id resolution that consumes them.
"""
import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.auth_users.models import Branch, generate_sync_token
from apps.core.middleware import DeploymentContextMiddleware
from apps.sync.registry import NEVER_SYNCED, is_synced, schema_version_for


# ---------------------------------------------------------------------------
# Model defaults — standalone installs must be untouched
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_new_branch_identity_defaults_are_standalone_safe(new_branch):
    """A branch created without cloud fields is the 'not enrolled' state."""
    assert new_branch.is_hq is False
    assert new_branch.cloud_id is None
    assert new_branch.sync_token is None
    assert new_branch.last_synced_at is None
    assert new_branch.is_active is True


def test_generate_sync_token_is_unguessable_and_fits_column():
    a = generate_sync_token()
    b = generate_sync_token()
    assert a != b
    assert 0 < len(a) <= 64


# ---------------------------------------------------------------------------
# EnrolmentCode is cloud-only — never replicated
# ---------------------------------------------------------------------------


def test_enrolment_code_is_never_synced():
    from apps.sync.models import EnrolmentCode

    table = EnrolmentCode._meta.db_table
    assert table in NEVER_SYNCED
    assert schema_version_for(table) is None
    assert not is_synced(table)


# ---------------------------------------------------------------------------
# Middleware branch_id resolution (§2.3)
# ---------------------------------------------------------------------------


def _stamp(request):
    mw = DeploymentContextMiddleware(lambda r: HttpResponse())
    mw(request)
    return request.branch_id


@override_settings(SYNC_ENABLED=False, BRANCH_ID="HQ")
@pytest.mark.django_db
def test_standalone_uses_env_branch_id_even_if_a_cloud_id_exists(new_branch):
    """Sync off: the fixed env constant wins, unconditionally (Phase 1)."""
    Branch.objects.filter(pk=new_branch.pk).update(cloud_id="SHOULD-BE-IGNORED")
    assert _stamp(RequestFactory().get("/")) == "HQ"


@override_settings(SYNC_ENABLED=True, BRANCH_ID="HQ")
@pytest.mark.django_db
def test_branch_device_stamps_enrolled_cloud_id(new_branch):
    Branch.objects.filter(pk=new_branch.pk).update(cloud_id="branch-uuid-123")
    assert _stamp(RequestFactory().get("/")) == "branch-uuid-123"


@override_settings(SYNC_ENABLED=True, BRANCH_ID="HQ")
@pytest.mark.django_db
def test_sync_on_but_not_yet_enrolled_falls_back_to_env(new_branch):
    """cloud_id still NULL (pre-enrolment) → env default, so nothing breaks."""
    assert _stamp(RequestFactory().get("/")) == "HQ"


@override_settings(SYNC_ENABLED=True, BRANCH_ID="HQ")
@pytest.mark.django_db
def test_deactivated_branch_is_not_used_as_identity(new_branch):
    Branch.objects.filter(pk=new_branch.pk).update(
        cloud_id="branch-uuid-123", is_active=False
    )
    assert _stamp(RequestFactory().get("/")) == "HQ"
