"""
Guards the sync registry (Phase 2 design §8.3, §8.4).

The most valuable test here is test_every_basemodel_table_is_classified:
it fails whenever someone adds a model without deciding whether it
syncs, which is exactly the mistake that would otherwise surface as
silently missing cloud data months later.
"""
import pytest
from django.apps import apps as django_apps

from apps.core.models import BaseModel
from apps.sync.registry import (
    NEVER_SYNCED,
    SYNCED_TABLES,
    UnregisteredTableError,
    is_synced,
    schema_version_for,
)

# Apps whose models participate in sync decisions at all. Django's own
# apps (admin, sessions, contenttypes) and DRF's authtoken are
# infrastructure, never replicated.
PROJECT_APP_LABELS = {
    "core",
    "auth_users",
    "inventory",
    "sales",
    "printing",
    "suppliers",
    "dashboard",
    "sync",
}


def _project_models():
    for model in django_apps.get_models():
        if model._meta.app_label in PROJECT_APP_LABELS:
            yield model


def test_registered_table_names_resolve_to_real_models():
    """A typo in either dict would silently disable sync for that table."""
    real_tables = {m._meta.db_table for m in _project_models()}

    for table in SYNCED_TABLES:
        assert table in real_tables, f"SYNCED_TABLES has unknown table {table!r}"

    for table in NEVER_SYNCED:
        assert table in real_tables, f"NEVER_SYNCED has unknown table {table!r}"


def test_no_table_is_both_synced_and_excluded():
    overlap = set(SYNCED_TABLES) & set(NEVER_SYNCED)
    assert not overlap, f"Tables in both registries: {overlap}"


def test_every_basemodel_table_is_classified():
    """
    Every BaseModel subclass carries sync columns (branch_id, synced_at,
    version), so each one must be explicitly classified. An unclassified
    model means someone added a synced-shaped table without deciding
    what happens to it.
    """
    unclassified = [
        model._meta.db_table
        for model in _project_models()
        if issubclass(model, BaseModel)
        and model._meta.db_table not in SYNCED_TABLES
        and model._meta.db_table not in NEVER_SYNCED
    ]
    assert not unclassified, (
        f"These BaseModel tables are in neither SYNCED_TABLES nor "
        f"NEVER_SYNCED: {unclassified}. Classify them in "
        f"apps/sync/registry.py."
    )


def test_held_sale_is_excluded():
    """§8.4 — transient, hard-deleted on restore, till-local."""
    from apps.sales.models import HeldSale

    assert HeldSale._meta.db_table in NEVER_SYNCED
    assert schema_version_for(HeldSale._meta.db_table) is None
    assert not is_synced(HeldSale._meta.db_table)


def test_catalogue_tables_are_synced():
    """
    Product and Category are the HQ -> branch catalogue layer
    (feasibility §6) — the whole point of pull. These were the tables
    missing outbox coverage before §8.2.
    """
    from apps.inventory.models import Category, Product

    assert is_synced(Product._meta.db_table)
    assert is_synced(Category._meta.db_table)


def test_unknown_table_raises():
    with pytest.raises(UnregisteredTableError):
        schema_version_for("some_app_somemodel")


def test_schema_versions_are_positive_integers():
    for table, version in SYNCED_TABLES.items():
        assert isinstance(version, int) and version >= 1, (
            f"{table} has invalid schema version {version!r}"
        )
