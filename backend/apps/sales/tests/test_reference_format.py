"""
Branch-scoped sale references (Phase 2 design §8.1).

Before this change every install generated BLD-<year>-<seq> from its own
database, so two branches would both produce BLD-2026-0001 and the
second one's push would be permanently rejected by the cloud's unique
constraint. The branch code is what prevents that.
"""
import re

import pytest

from apps.auth_users.models import Branch, BledgerUser, derive_branch_code
from apps.inventory.models import Category, Product
from apps.sales.models import Sale

from .conftest import api_client_for

REFERENCE_RE = re.compile(r"^BLD-[A-Z0-9]+-\d{4}-\d{4,}$")


def _sell(client, product, quantity=1):
    return client.post(
        "/api/v1/sales/",
        {"payment_method": "cash", "items": [{"product": str(product.id), "quantity": quantity}]},
        format="json",
    )


@pytest.mark.django_db
def test_reference_includes_branch_code(cashier_user, product):
    response = _sell(api_client_for(cashier_user), product)

    assert response.status_code == 201
    reference = response.data["reference"]
    assert REFERENCE_RE.match(reference), f"unexpected format: {reference!r}"
    assert reference.startswith("BLD-BUE-"), reference


@pytest.mark.django_db
def test_sequence_increments_per_branch(cashier_user, product):
    client = api_client_for(cashier_user)

    first = _sell(client, product).data["reference"]
    second = _sell(client, product).data["reference"]

    assert first.endswith("-0001")
    assert second.endswith("-0002")


@pytest.mark.django_db
def test_two_branches_do_not_collide(db, branch, category, product):
    """
    The core §8.1 guarantee: identical sequence numbers at two branches
    produce different references, so both survive a shared unique
    constraint.
    """
    other_branch = Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Douala Branch",
        phone="677999888",
        deployment_mode=Branch.DEPLOYMENT_STANDALONE,
        setup_complete=True,
        code="DLA",
    )
    cashier_a = BledgerUser.objects.create_user(
        branch=branch, name="Ambe J.", username="ambe", role="cashier", pin="1234"
    )
    cashier_b = BledgerUser.objects.create_user(
        branch=other_branch, name="Njoya P.", username="njoya", role="cashier", pin="4321"
    )

    ref_a = _sell(api_client_for(cashier_a), product).data["reference"]
    ref_b = _sell(api_client_for(cashier_b), product).data["reference"]

    # Same sequence number at both branches...
    assert ref_a.endswith("-0001")
    assert ref_b.endswith("-0001")
    # ...but distinct references, which is the whole point.
    assert ref_a != ref_b
    assert Sale.objects.filter(reference__in=[ref_a, ref_b]).count() == 2


@pytest.mark.django_db
def test_receipt_sale_number_is_still_the_sequence_tail(cashier_user, product):
    """
    The receipt shows "Sale #0001" — the tail, not the whole reference.
    Taking the last hyphen-separated segment must survive the format
    change.
    """
    from apps.sales.receipt_data import build_receipt_context

    reference = _sell(api_client_for(cashier_user), product).data["reference"]
    sale = Sale.objects.get(reference=reference)

    context = build_receipt_context(sale)
    assert context["sale_number"] == "0001"
    assert context["reference"] == reference


class TestDeriveBranchCode:
    def test_takes_first_three_letters_of_first_name(self):
        assert derive_branch_code("Buea Main Branch") == "BUE"

    def test_falls_back_to_later_names(self):
        assert derive_branch_code("", "Tabi Provisions") == "TAB"

    def test_strips_non_letters(self):
        assert derive_branch_code("3rd Street Shop") == "RDS"

    def test_falls_back_to_default_when_no_letters(self):
        assert derive_branch_code("123", "456") == "HQ"

    def test_suffixes_when_code_is_taken(self):
        """
        Branch.code is unique — two branches with similar names must not
        both derive BUE, or the second setup would fail.
        """
        assert derive_branch_code("Buea Main", taken=["BUE"]) == "BUE2"
        assert derive_branch_code("Buea Main", taken=["BUE", "BUE2"]) == "BUE3"

    def test_is_case_insensitive_about_taken_codes(self):
        assert derive_branch_code("Buea Main", taken=["bue"]) == "BUE2"
