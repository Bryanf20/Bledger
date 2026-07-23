"""Self-contained fixtures for the customers test suite (same pattern as
apps.suppliers.tests.conftest)."""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.customers.models import Customer

BRANCH_ID = "HQ"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        phone="677123456",
        deployment_mode="standalone",
        setup_complete=True,
        code="BUE",
    )


@pytest.fixture
def owner_user(db, branch):
    return BledgerUser.objects.create_user(
        branch=branch, name="Bea Owner", username="owner1", role="owner", password="ownerpass123"
    )


@pytest.fixture
def manager_user(db, branch):
    u = BledgerUser.objects.create_user(
        branch=branch, name="Manny Manager", username="manager1", role="manager", password="managerpass123"
    )
    u.set_pin("4321")
    u.save(update_fields=["pin_hash"])
    return u


@pytest.fixture
def cashier_user(db, branch):
    u = BledgerUser.objects.create_user(
        branch=branch, name="Cash Cashier", username="cashier1", role="cashier"
    )
    u.set_pin("1234")
    u.save()
    return u


@pytest.fixture
def customer(db):
    return Customer.objects.create(
        branch_id=BRANCH_ID, name="Ngwa Peter", phone="699000111", credit_limit=50000
    )


def api_client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def owner_client(owner_user):
    return api_client_for(owner_user)


@pytest.fixture
def manager_client(manager_user):
    return api_client_for(manager_user)


@pytest.fixture
def cashier_client(cashier_user):
    return api_client_for(cashier_user)
