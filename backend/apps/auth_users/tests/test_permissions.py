import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.auth_users.models import BledgerUser


@pytest.fixture
def api_client():
    return APIClient()


def _auth(api_client, user):
    token = Token.objects.create(user=user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return api_client


# -- model-level role helpers ---------------------------------------------


@pytest.mark.django_db
def test_role_properties(owner_user, manager_user, cashier_user):
    assert owner_user.is_owner and not owner_user.is_manager and not owner_user.is_cashier
    assert manager_user.is_manager and not manager_user.is_owner
    assert cashier_user.is_cashier and not cashier_user.is_owner


@pytest.mark.django_db
def test_set_pin_requires_four_digits(cashier_user):
    with pytest.raises(ValueError):
        cashier_user.set_pin("12")
    with pytest.raises(ValueError):
        cashier_user.set_pin("abcd")


@pytest.mark.django_db
def test_pin_is_hashed_not_stored_in_plaintext(cashier_user):
    assert cashier_user.pin_hash != "1234"
    assert cashier_user.check_pin("1234") is True
    assert cashier_user.check_pin("0000") is False


@pytest.mark.django_db
def test_has_pin_reflects_whether_pin_is_set(owner_user, cashier_user):
    assert owner_user.has_pin is False
    assert cashier_user.has_pin is True


# -- POST /api/v1/users/ — owner-only staff creation -----------------------


@pytest.mark.django_db
def test_owner_can_create_cashier(api_client, owner_user, branch):
    _auth(api_client, owner_user)
    response = api_client.post(
        "/api/v1/users/",
        {"name": "New Cashier", "username": "newcashier", "role": "cashier", "pin": "5678"},
    )
    assert response.status_code == 201
    created = BledgerUser.objects.get(username="newcashier")
    assert created.branch_id == branch.id
    assert created.check_pin("5678")


@pytest.mark.django_db
def test_owner_can_create_manager(api_client, owner_user):
    _auth(api_client, owner_user)
    response = api_client.post(
        "/api/v1/users/",
        {
            "name": "New Manager",
            "username": "newmanager",
            "role": "manager",
            "password": "managerpass123",
        },
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_cashier_role_without_pin_rejected(api_client, owner_user):
    _auth(api_client, owner_user)
    response = api_client.post(
        "/api/v1/users/", {"name": "No Pin", "username": "nopin", "role": "cashier"}
    )
    assert response.status_code == 400
    assert "pin" in response.data


@pytest.mark.django_db
def test_manager_role_without_password_rejected(api_client, owner_user):
    _auth(api_client, owner_user)
    response = api_client.post(
        "/api/v1/users/", {"name": "No Pass", "username": "nopass", "role": "manager"}
    )
    assert response.status_code == 400
    assert "password" in response.data


@pytest.mark.django_db
def test_manager_cannot_create_users(api_client, manager_user):
    _auth(api_client, manager_user)
    response = api_client.post(
        "/api/v1/users/",
        {"name": "X", "username": "x", "role": "cashier", "pin": "1111"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_cashier_cannot_create_users(api_client, cashier_user):
    _auth(api_client, cashier_user)
    response = api_client.post(
        "/api/v1/users/",
        {"name": "X", "username": "x", "role": "cashier", "pin": "1111"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_duplicate_username_rejected(api_client, owner_user, cashier_user):
    _auth(api_client, owner_user)
    response = api_client.post(
        "/api/v1/users/",
        {"name": "Dup", "username": cashier_user.username, "role": "cashier", "pin": "2222"},
    )
    assert response.status_code == 400
    assert "username" in response.data
    