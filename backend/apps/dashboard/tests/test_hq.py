"""
HQ multi-branch dashboard (Phase 2 design §2.4 / §2.6) — owner-only cross-
branch aggregation with per-branch breakdown and last-seen.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.auth_users.models import Branch
from apps.sales.models import Sale

HQ_URL = reverse("hq-summary")


def _sale(branch_id, cashier, amount, ref):
    return Sale.objects.create(
        branch_id=branch_id, cashier=cashier, payment_method=Sale.CASH,
        subtotal=amount, total_amount=amount, reference=ref,
    )


@pytest.mark.django_db
def test_hq_summary_requires_owner(manager_client):
    assert manager_client.get(HQ_URL).status_code == 403


@pytest.mark.django_db
def test_hq_summary_aggregates_across_branches(owner_client, owner_user, branch):
    # The conftest branch is HQ: its records carry settings.BRANCH_ID ("HQ").
    Branch.objects.filter(pk=branch.pk).update(is_hq=True)
    _sale("HQ", owner_user, 5000, "R1")
    _sale("HQ", owner_user, 3000, "R2")

    other = Branch.objects.create(
        business_name="Tabi Provisions", branch_name="Limbe", phone="699",
        code="LMB", deployment_mode=Branch.DEPLOYMENT_CONNECTED, setup_complete=True,
    )
    _sale(str(other.id), owner_user, 2000, "R3")

    body = owner_client.get(HQ_URL).json()
    assert body["total_revenue"] == 10000
    assert body["total_transactions"] == 3
    assert body["branch_count"] == 2

    by_code = {r["code"]: r for r in body["branches"]}
    assert by_code["BUE"]["revenue"] == 8000
    assert by_code["BUE"]["transaction_count"] == 2
    assert by_code["BUE"]["is_hq"] is True
    assert by_code["LMB"]["revenue"] == 2000
    assert by_code["LMB"]["transaction_count"] == 1


@pytest.mark.django_db
def test_hq_summary_includes_idle_branches(owner_client, branch):
    Branch.objects.create(
        business_name="Tabi Provisions", branch_name="Idle Shop", phone="699",
        code="IDL", deployment_mode=Branch.DEPLOYMENT_CONNECTED, setup_complete=True,
    )
    body = owner_client.get(HQ_URL).json()
    idle = next(r for r in body["branches"] if r["code"] == "IDL")
    assert idle["revenue"] == 0
    assert idle["transaction_count"] == 0


@pytest.mark.django_db
def test_hq_summary_reports_last_synced_and_active(owner_client, branch):
    ts = timezone.now()
    Branch.objects.filter(pk=branch.pk).update(last_synced_at=ts, is_active=True)
    body = owner_client.get(HQ_URL).json()
    row = next(r for r in body["branches"] if r["code"] == "BUE")
    assert row["last_synced_at"] is not None
    assert row["is_active"] is True
