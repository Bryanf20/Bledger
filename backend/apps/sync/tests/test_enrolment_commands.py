"""
CLI enrolment path (Phase 2 design §2.3): provision_branch (cloud) mints a
code; enrol_device (branch) redeems it and persists the cloud identity.
"""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.auth_users.models import Branch
from apps.sync.enrolment import persist_enrolment
from apps.sync.models import EnrolmentCode


@pytest.mark.django_db
def test_provision_branch_creates_branch_and_code():
    out = StringIO()
    call_command("provision_branch", "--branch-name", "Limbe Branch", "--code", "LMB", stdout=out)

    branch = Branch.objects.get(code="LMB")
    assert branch.deployment_mode == Branch.DEPLOYMENT_CONNECTED
    assert branch.setup_complete is False
    ec = EnrolmentCode.objects.get(branch=branch)
    assert ec.code in out.getvalue()
    assert ec.is_valid()


@pytest.mark.django_db
def test_provision_branch_derives_code_when_omitted():
    call_command("provision_branch", "--branch-name", "Kumba Shop", stdout=StringIO())
    assert Branch.objects.filter(branch_name="Kumba Shop").exists()


@pytest.mark.django_db
def test_provision_branch_rejects_duplicate_code():
    Branch.objects.create(
        business_name="X", branch_name="A", code="DUP",
        deployment_mode=Branch.DEPLOYMENT_CONNECTED, setup_complete=False,
    )
    with pytest.raises(CommandError):
        call_command("provision_branch", "--branch-name", "B", "--code", "DUP", stdout=StringIO())


@pytest.mark.django_db
def test_persist_enrolment_creates_local_branch_identity():
    branch = persist_enrolment({
        "branch_id": "11111111-1111-1111-1111-111111111111",
        "sync_token": "tok-xyz",
        "code": "LMB",
        "business_name": "Tabi Provisions",
        "branch_name": "Limbe Branch",
        "is_hq": False,
    })
    assert branch.cloud_id == "11111111-1111-1111-1111-111111111111"
    assert str(branch.id) == "11111111-1111-1111-1111-111111111111"
    assert branch.sync_token == "tok-xyz"
    assert branch.setup_complete is True
    assert branch.deployment_mode == Branch.DEPLOYMENT_CONNECTED


@pytest.mark.django_db
def test_persist_enrolment_updates_existing_branch():
    Branch.objects.create(
        business_name="Old", branch_name="Old", code="OLD",
        deployment_mode=Branch.DEPLOYMENT_STANDALONE, setup_complete=True,
    )
    branch = persist_enrolment({
        "branch_id": "22222222-2222-2222-2222-222222222222", "sync_token": "tok-9", "code": "NEW",
        "business_name": "New Biz", "branch_name": "New Branch", "is_hq": True,
    })
    assert Branch.objects.count() == 1  # updated in place, not duplicated
    assert branch.cloud_id == "22222222-2222-2222-2222-222222222222"
    assert branch.is_hq is True
