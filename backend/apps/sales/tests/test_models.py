import pytest

from apps.sales.models import HeldSale, Sale


@pytest.mark.django_db
def test_sale_str_returns_reference(owner_user):
    sale = Sale.objects.create(
        branch_id="HQ", cashier=owner_user, reference="BLD-2026-0001",
        payment_method="cash", subtotal=1000, total_amount=1000,
    )
    assert str(sale) == "BLD-2026-0001"


@pytest.mark.django_db
def test_held_sale_held_at_aliases_created_at(cashier_user):
    held = HeldSale.objects.create(branch_id="HQ", cashier=cashier_user, cart_data={"items": []})
    assert held.held_at == held.created_at
    