"""
Device-side POST /api/v1/sync/connect/ — the setup-wizard "Connect to head
office" path (Phase 2 design §2.3). The cloud HTTP call is mocked; the
device-side persist + response are what's under test.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

import apps.sync.views as views_module
from apps.auth_users.models import Branch
from apps.sync.enrolment import EnrolmentError

CONNECT_URL = reverse("sync-connect")

CLOUD_BID = "55555555-5555-5555-5555-555555555555"
FAKE_RESPONSE = {
    "branch_id": CLOUD_BID,
    "sync_token": "tok-connect",
    "code": "LMB",
    "business_name": "Tabi Provisions",
    "branch_name": "Limbe Branch",
    "is_hq": False,
    "deployment_mode": "connected",
}


@pytest.mark.django_db
def test_connect_enrols_and_persists_identity(monkeypatch):
    monkeypatch.setattr(views_module, "call_enrol", lambda url, code: dict(FAKE_RESPONSE))

    resp = APIClient().post(
        CONNECT_URL, {"code": "lmb-code", "cloud_url": "https://hq.example.com"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["branch_name"] == "Limbe Branch"
    assert body["code"] == "LMB"

    branch = Branch.objects.get()
    assert str(branch.id) == CLOUD_BID          # pk aligned with cloud id
    assert branch.cloud_id == CLOUD_BID
    assert branch.sync_token == "tok-connect"
    assert branch.setup_complete is True
    assert branch.deployment_mode == Branch.DEPLOYMENT_CONNECTED


@pytest.mark.django_db
def test_connect_requires_a_code(monkeypatch):
    resp = APIClient().post(CONNECT_URL, {"cloud_url": "https://hq.example.com"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_connect_requires_a_cloud_url(monkeypatch):
    resp = APIClient().post(CONNECT_URL, {"code": "ABCD"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_connect_surfaces_enrolment_failure(monkeypatch):
    def boom(url, code):
        raise EnrolmentError("Enrolment rejected (HTTP 409): already used")

    monkeypatch.setattr(views_module, "call_enrol", boom)
    resp = APIClient().post(
        CONNECT_URL, {"code": "used", "cloud_url": "https://hq.example.com"}, format="json"
    )
    assert resp.status_code == 400
    assert "already used" in resp.json()["detail"]
