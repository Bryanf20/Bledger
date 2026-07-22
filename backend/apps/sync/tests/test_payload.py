"""
Payload serialization contract (Phase 2 design §8.3).

The previous implementation str()'d anything non-primitive, so a UUID, a
date and a foreign key all arrived as strings of differing shape with no
way for the cloud to tell them apart. These tests pin the typed
behaviour that replaced it.
"""
import datetime
import uuid

import pytest

from apps.auth_users.models import Branch, BledgerUser
from apps.inventory.models import Category, Product
from apps.sales.models import HeldSale
from apps.sync.models import OutboxEntry
from apps.sync.utils import serialize_instance, write_outbox_entry

BRANCH_ID = "HQ"


@pytest.fixture
def branch(db):
    return Branch.objects.create(
        business_name="Tabi Provisions",
        branch_name="Buea Main Branch",
        phone="677123456",
        deployment_mode=Branch.DEPLOYMENT_STANDALONE,
        setup_complete=True,
        code="BUE",
    )


@pytest.fixture
def category(db):
    return Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        branch_id=BRANCH_ID,
        name="Mama Gold rice 5kg",
        category=category,
        unit="bag",
        retail_price=4500,
        stock_level=50,
    )


def test_payload_is_json_serializable(product):
    """
    The whole point — a payload that json.dumps() rejects is an entry
    that can never be pushed.
    """
    import json

    payload = serialize_instance(product)
    json.dumps(payload)  # must not raise


def test_uuid_pk_serializes_as_canonical_string(product):
    payload = serialize_instance(product)
    assert payload["id"] == str(product.id)
    # Round-trips back to the same UUID — not a repr or truncated form.
    assert uuid.UUID(payload["id"]) == product.id


def test_foreign_key_serializes_as_id_not_nested_object(product, category):
    """
    FKs go out as `<field>_id`, so the cloud never has to unpack a
    nested object and serialization never triggers a lazy DB fetch.
    """
    payload = serialize_instance(product)

    assert payload["category_id"] == str(category.id)
    assert "category" not in payload


def test_datetimes_are_utc_iso_with_z_suffix(product):
    payload = serialize_instance(product)

    created = payload["created_at"]
    assert created.endswith("Z"), f"expected Z-suffixed UTC, got {created!r}"
    # Parseable back to an aware datetime.
    parsed = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_none_stays_null_not_the_string_none(product):
    """
    The old str() approach turned None into "None", which the cloud
    would have stored as a literal string.
    """
    product.bulk_price = None
    product.save(update_fields=["bulk_price"])

    payload = serialize_instance(product)
    assert payload["bulk_price"] is None


def test_integers_stay_integers(product):
    """XAF money must not arrive as a string — it is integer throughout."""
    payload = serialize_instance(product)

    assert payload["retail_price"] == 4500
    assert isinstance(payload["retail_price"], int)
    assert isinstance(payload["stock_level"], int)


def test_booleans_stay_booleans(product):
    payload = serialize_instance(product)
    assert payload["is_active"] is True


def test_write_outbox_entry_stamps_schema_version(product):
    entry = write_outbox_entry(instance=product, operation=OutboxEntry.INSERT)

    assert entry is not None
    assert entry.schema_version == 1
    assert entry.table_name == "inventory_product"
    assert entry.record_id == product.id


def test_write_outbox_entry_skips_never_synced_tables(db, branch):
    """
    HeldSale is excluded (§8.4). write_outbox_entry() returns None and
    writes nothing, so callers can call it unconditionally.
    """
    cashier = BledgerUser.objects.create_user(
        branch=branch, name="Ambe J.", username="ambe", role="cashier", pin="1234"
    )
    held = HeldSale.objects.create(
        branch_id=BRANCH_ID, cashier=cashier, label="Woman in red", cart_data={"items": []}
    )

    before = OutboxEntry.objects.count()
    result = write_outbox_entry(instance=held, operation=OutboxEntry.INSERT)

    assert result is None
    assert OutboxEntry.objects.count() == before
