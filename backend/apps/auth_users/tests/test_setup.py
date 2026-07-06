import pytest
from rest_framework.test import APIClient

from apps.auth_users.models import Branch


@pytest.fixture
def api_client():
    return APIClient()


SETUP_PAYLOAD = {
    "business_name": "Tabi Provisions",
    "branch_name": "Buea Main Branch",
    "phone": "677123456",
    "owner_name": "Ayuk N.",
    "username": "ayuk",
    "password": "ownerpass123",
}


@pytest.mark.django_db
def test_setup_status_false_before_setup(api_client):
    response = api_client.get("/api/v1/setup/status/")
    assert response.status_code == 200
    assert response.data["setup_complete"] is False


@pytest.mark.django_db
def test_setup_creates_branch_and_owner_and_logs_in(api_client):
    response = api_client.post("/api/v1/setup/", SETUP_PAYLOAD)
    assert response.status_code == 201
    assert response.data["token"]
    assert response.data["user"]["role"] == "owner"
    assert response.data["user"]["branch"]["business_name"] == "Tabi Provisions"

    branch = Branch.objects.get(business_name="Tabi Provisions")
    assert branch.setup_complete is True
    assert branch.users.count() == 1
    assert branch.users.first().username == "ayuk"


@pytest.mark.django_db
def test_setup_status_true_after_setup(api_client):
    api_client.post("/api/v1/setup/", SETUP_PAYLOAD)
    response = api_client.get("/api/v1/setup/status/")
    assert response.data["setup_complete"] is True


@pytest.mark.django_db
def test_setup_cannot_run_twice(api_client):
    api_client.post("/api/v1/setup/", SETUP_PAYLOAD)
    response = api_client.post(
        "/api/v1/setup/", {**SETUP_PAYLOAD, "username": "someoneelse"}
    )
    assert response.status_code == 409


@pytest.mark.django_db
def test_setup_rejects_short_password(api_client):
    response = api_client.post("/api/v1/setup/", {**SETUP_PAYLOAD, "password": "short"})
    assert response.status_code == 400
    assert "password" in response.data


@pytest.mark.django_db
def test_setup_with_optional_pin(api_client):
    response = api_client.post("/api/v1/setup/", {**SETUP_PAYLOAD, "pin": "9999"})
    assert response.status_code == 201
    assert response.data["user"]["has_pin"] is True


@pytest.mark.django_db
def test_load_template_success(api_client):
    setup_response = api_client.post("/api/v1/setup/", SETUP_PAYLOAD)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {setup_response.data['token']}")

    response = api_client.post(
        "/api/v1/setup/load-template/", {"template_key": "provision-store"}
    )
    assert response.status_code == 201
    assert response.data["categories_created"] == 6
    assert response.data["products_created"] == 12


@pytest.mark.django_db
def test_load_template_requires_template_key(api_client):
    setup_response = api_client.post("/api/v1/setup/", SETUP_PAYLOAD)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {setup_response.data['token']}")

    response = api_client.post("/api/v1/setup/load-template/", {})
    assert response.status_code == 400


@pytest.mark.django_db
def test_load_template_rejects_unknown_key(api_client):
    setup_response = api_client.post("/api/v1/setup/", SETUP_PAYLOAD)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {setup_response.data['token']}")

    response = api_client.post(
        "/api/v1/setup/load-template/", {"template_key": "nonexistent"}
    )
    assert response.status_code == 404
    