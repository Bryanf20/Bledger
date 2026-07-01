import pytest

from apps.auth_users.models import BledgerUser, Branch


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        phone="677123456",
        deployment_mode=Branch.DEPLOYMENT_STANDALONE,
        setup_complete=True,
    )


@pytest.fixture
def owner_user(branch):
    return BledgerUser.objects.create_user(
        username="ayuk",
        branch=branch,
        role=BledgerUser.ROLE_OWNER,
        password="ownerpass123",
        name="Ayuk N.",
    )


@pytest.fixture
def manager_user(branch):
    return BledgerUser.objects.create_user(
        username="manyi",
        branch=branch,
        role=BledgerUser.ROLE_MANAGER,
        password="managerpass123",
        name="Manyi T.",
    )


@pytest.fixture
def cashier_user(branch):
    return BledgerUser.objects.create_user(
        username="ambe",
        branch=branch,
        role=BledgerUser.ROLE_CASHIER,
        pin="1234",
        name="Ambe J.",
    )
