"""
NOTE ON ASSUMPTIONS: this conftest is written against the *documented*
shape of apps.auth_users (Branch / BledgerUser / create_user / set_pin)
from the design doc and the auth_users build summary, not against its
actual source, which isn't in this app's context. If Branch's primary
key, BledgerUser.objects.create_user()'s signature, or set_pin() differ
from what's assumed below, update this file to match auth_users/tests/
conftest.py rather than the other way around.
"""
import pytest
from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.auth_users.models import Branch, BledgerUser
from apps.inventory.models import Category, Product

# apps.core.middleware.DeploymentContextMiddleware stamps request.branch_id
# from settings.BRANCH_ID (a fixed string per standalone install), NOT
# from a DB lookup on Branch. So API-level fixtures create inventory rows
# under settings.BRANCH_ID directly, rather than under branch.id, to
# guarantee they land in the same scope the view queries will use —
# independent of whatever type Branch's own primary key turns out to be.
BRANCH_ID = settings.BRANCH_ID


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        address="Molyko, Buea",
        phone="677123456",
        deployment_mode="standalone",
        setup_complete=True,
    )


@pytest.fixture
def owner_user(branch):
    return BledgerUser.objects.create_user(
        branch=branch, username="owner1", name="Owner One", role="owner", password="testpass123"
    )


@pytest.fixture
def manager_user(branch):
    return BledgerUser.objects.create_user(
        branch=branch, username="manager1", name="Manager One", role="manager", password="testpass123"
    )


@pytest.fixture
def cashier_user(branch):
    user = BledgerUser.objects.create_user(
        branch=branch, username="cashier1", name="Cashier One", role="cashier"
    )
    user.set_pin("1234")
    user.set_unusable_password()
    user.save()
    return user


def _client_for(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def owner_client(owner_user):
    return _client_for(owner_user)


@pytest.fixture
def manager_client(manager_user):
    return _client_for(manager_user)


@pytest.fixture
def cashier_client(cashier_user):
    return _client_for(cashier_user)


@pytest.fixture
def category(branch):
    return Category.objects.create(branch_id=BRANCH_ID, name="Grains & Staples", sort_order=1)


@pytest.fixture
def product(branch, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Mama Gold rice 5kg",
        category=category,
        unit="bag",
        retail_price=4500,
        bulk_price=4000,
        bulk_min_qty=12,
        stock_level=20,
        low_stock_threshold=5,
    )
