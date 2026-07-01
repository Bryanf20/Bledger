import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


# -- username/password login (owner, manager) -------------------------------


@pytest.mark.django_db
def test_login_success_returns_token_and_profile(api_client, owner_user):
    response = api_client.post(
        "/api/v1/auth/login/", {"username": "ayuk", "password": "ownerpass123"}
    )
    assert response.status_code == 200
    assert response.data["token"]
    assert response.data["user"]["username"] == "ayuk"
    assert response.data["user"]["role"] == "owner"
    assert response.data["user"]["branch"]["business_name"] == "Tabi Provisions"
    assert Token.objects.filter(user=owner_user).exists()


@pytest.mark.django_db
def test_login_wrong_password_rejected(api_client, owner_user):
    response = api_client.post(
        "/api/v1/auth/login/", {"username": "ayuk", "password": "wrong"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_login_unknown_username_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/login/", {"username": "nobody", "password": "whatever123"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_login_inactive_user_rejected(api_client, owner_user):
    owner_user.is_active = False
    owner_user.save()
    response = api_client.post(
        "/api/v1/auth/login/", {"username": "ayuk", "password": "ownerpass123"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_cashier_cannot_use_password_login(api_client, cashier_user):
    # Cashiers are created with an unusable password (PIN-only account).
    response = api_client.post(
        "/api/v1/auth/login/", {"username": "ambe", "password": "1234"}
    )
    assert response.status_code == 400


# -- PIN login (cashier) -----------------------------------------------------


@pytest.mark.django_db
def test_pin_login_success(api_client, cashier_user):
    response = api_client.post(
        "/api/v1/auth/pin-login/", {"username": "ambe", "pin": "1234"}
    )
    assert response.status_code == 200
    assert response.data["user"]["role"] == "cashier"


@pytest.mark.django_db
def test_pin_login_wrong_pin_rejected(api_client, cashier_user):
    response = api_client.post(
        "/api/v1/auth/pin-login/", {"username": "ambe", "pin": "9999"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_pin_login_rejects_non_digit_or_wrong_length(api_client, cashier_user):
    response = api_client.post(
        "/api/v1/auth/pin-login/", {"username": "ambe", "pin": "12"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_owner_without_pin_cannot_pin_login(api_client, owner_user):
    response = api_client.post(
        "/api/v1/auth/pin-login/", {"username": "ayuk", "pin": "1234"}
    )
    assert response.status_code == 400


# -- logout -------------------------------------------------------------------


@pytest.mark.django_db
def test_logout_invalidates_token(api_client, owner_user):
    token = Token.objects.create(user=owner_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    response = api_client.post("/api/v1/auth/logout/")
    assert response.status_code == 204
    assert not Token.objects.filter(user=owner_user).exists()


@pytest.mark.django_db
def test_logout_requires_authentication(api_client):
    response = api_client.post("/api/v1/auth/logout/")
    assert response.status_code == 401


# -- /auth/me/ ------------------------------------------------------------------


@pytest.mark.django_db
def test_me_returns_current_user_profile(api_client, manager_user):
    token = Token.objects.create(user=manager_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    response = api_client.get("/api/v1/auth/me/")
    assert response.status_code == 200
    assert response.data["username"] == "manyi"
    assert response.data["role"] == "manager"
    assert response.data["has_pin"] is False


@pytest.mark.django_db
def test_me_requires_authentication(api_client):
    response = api_client.get("/api/v1/auth/me/")
    assert response.status_code == 401