"""
Enrolment endpoints (Phase 2 design §2.3):

  POST /api/v1/sync/branches/  — owner provisions a branch + gets a code
  POST /api/v1/sync/enrol/     — a device redeems the code for its identity
"""
import pytest
from django.urls import reverse
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.auth_users.models import Branch
from apps.sync.models import EnrolmentCode

from .conftest import client_for


# ---------------------------------------------------------------------------
# Provisioning (owner-only)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_provisions_branch_and_gets_enrolment_code(owner_user):
    resp = client_for(owner_user).post(
        reverse("sync-branch-provision"),
        {"branch_name": "Kumba Branch", "code": "KMB"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["code"] == "KMB"
    assert body["is_hq"] is False
    assert body["enrolment_code"]

    branch = Branch.objects.get(id=body["branch_id"])
    assert branch.deployment_mode == Branch.DEPLOYMENT_CONNECTED
    assert branch.setup_complete is False
    # Business name is inherited from the provisioning owner's branch.
    assert branch.business_name == owner_user.branch.business_name
    assert EnrolmentCode.objects.filter(branch=branch).count() == 1


@pytest.mark.django_db
def test_provision_derives_code_when_omitted(owner_user):
    resp = client_for(owner_user).post(
        reverse("sync-branch-provision"),
        {"branch_name": "Mutengene Shop"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["code"]  # derived, non-empty


@pytest.mark.django_db
def test_provision_can_flag_hq(owner_user):
    resp = client_for(owner_user).post(
        reverse("sync-branch-provision"),
        {"branch_name": "Second HQ", "code": "HQ2", "is_hq": True},
        format="json",
    )
    assert resp.status_code == 201
    assert Branch.objects.get(id=resp.json()["branch_id"]).is_hq is True


@pytest.mark.django_db
def test_provision_rejects_duplicate_code(owner_user, new_branch):
    resp = client_for(owner_user).post(
        reverse("sync-branch-provision"),
        {"branch_name": "Clash", "code": new_branch.code},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_manager_cannot_provision_branches(manager_user):
    resp = client_for(manager_user).post(
        reverse("sync-branch-provision"),
        {"branch_name": "Nope"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_provision_branches(db):
    resp = APIClient().post(
        reverse("sync-branch-provision"), {"branch_name": "Nope"}, format="json"
    )
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Enrolment (device redeems a code — no auth)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_enrol_with_valid_code_returns_identity(new_branch, enrolment_code):
    resp = APIClient().post(
        reverse("sync-enrol"), {"code": enrolment_code.code}, format="json"
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()

    assert body["branch_id"] == str(new_branch.id)
    assert body["code"] == new_branch.code
    assert body["business_name"] == new_branch.business_name
    assert body["is_hq"] is False
    assert body["sync_token"]  # a real token was issued

    new_branch.refresh_from_db()
    assert new_branch.sync_token == body["sync_token"]

    enrolment_code.refresh_from_db()
    assert enrolment_code.is_consumed


@pytest.mark.django_db
def test_enrol_normalises_lowercase_and_whitespace(enrolment_code):
    messy = f"  {enrolment_code.code.lower()}  "
    resp = APIClient().post(reverse("sync-enrol"), {"code": messy}, format="json")
    assert resp.status_code == 200, resp.content


@pytest.mark.django_db
def test_enrol_is_single_use(enrolment_code):
    url = reverse("sync-enrol")
    first = APIClient().post(url, {"code": enrolment_code.code}, format="json")
    assert first.status_code == 200
    second = APIClient().post(url, {"code": enrolment_code.code}, format="json")
    assert second.status_code == 409


@pytest.mark.django_db
def test_enrol_rejects_expired_code(new_branch):
    expired = EnrolmentCode.objects.create(branch=new_branch)
    EnrolmentCode.objects.filter(pk=expired.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    resp = APIClient().post(reverse("sync-enrol"), {"code": expired.code}, format="json")
    assert resp.status_code == 410


@pytest.mark.django_db
def test_enrol_rejects_unknown_code(db):
    resp = APIClient().post(reverse("sync-enrol"), {"code": "ZZZZZZZZ"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_enrol_rejects_deactivated_branch(new_branch, enrolment_code):
    Branch.objects.filter(pk=new_branch.pk).update(is_active=False)
    resp = APIClient().post(
        reverse("sync-enrol"), {"code": enrolment_code.code}, format="json"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_enrol_preserves_existing_sync_token(new_branch, enrolment_code):
    Branch.objects.filter(pk=new_branch.pk).update(sync_token="pre-existing-token")
    resp = APIClient().post(
        reverse("sync-enrol"), {"code": enrolment_code.code}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["sync_token"] == "pre-existing-token"
