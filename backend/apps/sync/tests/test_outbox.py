import pytest

from apps.inventory.models import Category
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry


@pytest.mark.django_db
def test_write_outbox_entry_creates_row():
    category = Category.objects.create(branch_id="HQ", name="Drinks", sort_order=1)
    write_outbox_entry(instance=category, operation=OutboxEntry.INSERT)

    entry = OutboxEntry.objects.get(record_id=category.id)
    assert entry.table_name == category._meta.db_table
    assert entry.operation == OutboxEntry.INSERT
    assert entry.branch_id == "HQ"
    assert entry.payload["name"] == "Drinks"
    assert entry.synced_at is None