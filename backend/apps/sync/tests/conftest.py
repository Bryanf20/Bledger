"""
Fixtures for the Phase 2 enrolment tests (Stage 3, step 9). These model
the *cloud* side: an HQ owner who provisions branches, and the branch rows
+ enrolment codes that live on the cloud.
"""
import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import BledgerUser, Branch
from apps.sync.models import EnrolmentCode


@pytest.fixture
def hq_branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Head Office",
        phone="677123456",
        code="HQ",
        is_hq=True,
        deployment_mode=Branch.DEPLOYMENT_CONNECTED,
        setup_complete=True,
    )


@pytest.fixture
def owner_user(hq_branch):
    return BledgerUser.objects.create_user(
        username="ayuk",
        branch=hq_branch,
        role=BledgerUser.ROLE_OWNER,
        password="ownerpass123",
        name="Ayuk N.",
    )


@pytest.fixture
def manager_user(hq_branch):
    return BledgerUser.objects.create_user(
        username="manyi",
        branch=hq_branch,
        role=BledgerUser.ROLE_MANAGER,
        password="managerpass123",
        name="Manyi T.",
    )


@pytest.fixture
def new_branch(db):
    """A branch the cloud has provisioned but no device has enrolled yet."""
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Limbe Branch",
        phone="699000000",
        code="LMB",
        deployment_mode=Branch.DEPLOYMENT_CONNECTED,
        setup_complete=False,
    )


@pytest.fixture
def enrolment_code(new_branch):
    return EnrolmentCode.objects.create(branch=new_branch)


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c
