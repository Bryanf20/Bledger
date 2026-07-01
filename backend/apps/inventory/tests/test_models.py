import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.inventory.models import Category, Product

pytestmark = pytest.mark.django_db


def test_product_stock_status_ok(product):
    assert product.stock_status == "ok"


def test_product_stock_status_low(product):
    product.stock_level = product.low_stock_threshold
    assert product.stock_status == "low"


def test_product_stock_status_out(product):
    product.stock_level = 0
    assert product.stock_status == "out"


def test_bulk_price_requires_bulk_min_qty(branch, category):
    product = Product(
        branch_id=branch.id,
        name="Broken bulk product",
        category=category,
        retail_price=1000,
        bulk_price=900,  # no bulk_min_qty
    )
    with pytest.raises(ValidationError):
        product.full_clean()


def test_bulk_min_qty_requires_bulk_price(branch, category):
    product = Product(
        branch_id=branch.id,
        name="Broken bulk product",
        category=category,
        retail_price=1000,
        bulk_min_qty=12,  # no bulk_price
    )
    with pytest.raises(ValidationError):
        product.full_clean()


def test_category_name_unique_per_branch(branch):
    Category.objects.create(branch_id=branch.id, name="Drinks")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Category.objects.create(branch_id=branch.id, name="Drinks")


def test_category_name_can_repeat_across_branches(branch):
    Category.objects.create(branch_id=branch.id, name="Drinks")
    # Different branch_id, same name — no conflict.
    Category.objects.create(branch_id="other-branch", name="Drinks")


def test_category_soft_delete_frees_the_name(branch):
    cat = Category.objects.create(branch_id=branch.id, name="Drinks")
    cat.soft_delete()
    # The unique constraint only applies while deleted_at is null, so a
    # new category can reuse the name.
    Category.objects.create(branch_id=branch.id, name="Drinks")


def test_product_version_increments_on_save(product):
    assert product.version == 1
    product.name = "Mama Gold rice 5kg (relabelled)"
    product.save()
    product.refresh_from_db()
    assert product.version == 2
