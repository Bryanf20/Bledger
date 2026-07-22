"""
BaseModel's sync-facing columns (version, deleted_at).

`version` is the optimistic-concurrency counter the Phase 2 sync engine
relies on for catalogue records (feasibility §8.2), so a write that
fails to move it is a real defect even though nothing reads it yet in
Phase 1.
"""
import pytest

from apps.auth_users.models import Branch
from apps.inventory.models import Category

BRANCH_ID = "HQ"


@pytest.fixture
def category(db):
    return Category.objects.create(branch_id=BRANCH_ID, name="Grains", sort_order=1)


@pytest.mark.django_db
def test_version_starts_at_one(category):
    assert category.version == 1


@pytest.mark.django_db
def test_version_increments_on_update(category):
    category.name = "Grains & cereals"
    category.save()
    category.refresh_from_db()

    assert category.version == 2


@pytest.mark.django_db
def test_soft_delete_persists_version_increment(category):
    """
    Regression: soft_delete() saved with update_fields that omitted
    "version", so BaseModel.save()'s increment happened in memory and
    was then dropped by the restricted UPDATE.
    """
    assert category.version == 1

    category.soft_delete()
    category.refresh_from_db()

    assert category.deleted_at is not None
    assert category.version == 2, "soft_delete must persist the version bump"


@pytest.mark.django_db
def test_soft_deleted_rows_drop_out_of_default_manager(category):
    category.soft_delete()

    assert not Category.objects.filter(pk=category.pk).exists()
    assert Category.all_objects.filter(pk=category.pk).exists()
