"""
Product.barcode — optional scan code, unique per branch when set
(Phase 2 design §5).

The load-bearing properties: barcode is genuinely optional (many
products with none must coexist), it's unique per branch only when set,
the same code may legitimately exist at a different branch, and adding
it didn't disturb the outbox coverage from §8.2.
"""
import pytest

from apps.inventory.models import Category, Product
from apps.sync.models import OutboxEntry

from .conftest import BRANCH_ID

pytestmark = pytest.mark.django_db


def test_barcode_round_trips_through_api(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Peak milk 400g", "category": str(category.id), "retail_price": 1800, "barcode": "6001234500011"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["barcode"] == "6001234500011"


def test_barcode_is_optional(manager_client, category):
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Loose beans (cup)", "category": str(category.id), "retail_price": 200},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["barcode"] == ""


def test_many_products_may_have_no_barcode(category):
    """
    The uniqueness constraint must NOT trip on the empty string — most
    provision-store goods have no barcode at all.
    """
    for i in range(3):
        Product.objects.create(
            branch_id=BRANCH_ID, name=f"Unbarcoded {i}", category=category, retail_price=100
        )
    assert Product.objects.filter(barcode="").count() == 3


def test_duplicate_barcode_in_same_branch_rejected(manager_client, category, product):
    product.barcode = "6001234500011"
    product.save(update_fields=["barcode"])

    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Impostor", "category": str(category.id), "retail_price": 500, "barcode": "6001234500011"},
        format="json",
    )
    assert resp.status_code == 400
    assert "barcode" in resp.data


def test_editing_keeps_own_barcode(manager_client, category, product):
    product.barcode = "6001234500011"
    product.save(update_fields=["barcode"])

    # PATCHing the same product with its own barcode must not self-collide.
    resp = manager_client.patch(
        f"/api/v1/products/{product.id}/",
        {"barcode": "6001234500011", "retail_price": 4600},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["retail_price"] == 4600


def test_same_barcode_allowed_in_different_branch(category, product):
    """
    Uniqueness is per branch, not global — two branches can legitimately
    stock the same product with the same manufacturer barcode.
    """
    product.barcode = "6001234500011"
    product.save(update_fields=["barcode"])

    other_cat = Category.objects.create(branch_id="OTHER", name="Grains", sort_order=1)
    # No IntegrityError expected — different branch_id.
    other = Product.objects.create(
        branch_id="OTHER", name="Same milk elsewhere", category=other_cat,
        retail_price=1800, barcode="6001234500011",
    )
    assert other.pk is not None


def test_setting_barcode_still_writes_outbox(manager_client, category):
    """Product create carries barcode and still emits an outbox entry (§8.2)."""
    resp = manager_client.post(
        "/api/v1/products/",
        {"name": "Barcoded", "category": str(category.id), "retail_price": 900, "barcode": "5000159407236"},
        format="json",
    )
    assert resp.status_code == 201
    entry = OutboxEntry.objects.filter(record_id=resp.data["id"]).first()
    assert entry is not None
    assert entry.payload["barcode"] == "5000159407236"
