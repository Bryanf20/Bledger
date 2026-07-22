"""
Rewrites existing Sale.reference values into the branch-scoped format
BLD-<branch_code>-<year>-<seq> (Phase 2 design §8.1).

Old format: BLD-2026-0001
New format: BLD-BUE-2026-0001

Pure data migration — Sale.reference stays a unique CharField, only its
contents change. Confirmed with the project owner that there is no
production sales data at time of writing, so rewriting historical
references is safe. If that ever stops being true, the correct approach
is to leave old references untouched and apply the new format only to
sales created from here on (both remain unique, so they can coexist).

Branch code is resolved via the sale's cashier (Sale.cashier.branch),
because Sale.branch_id is BaseModel's free-text branch string rather
than a foreign key to Branch.
"""
import re

from django.db import migrations

OLD_REFERENCE_RE = re.compile(r"^BLD-(\d{4})-(\d+)$")


def add_branch_code(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")

    # all_objects isn't available on historical models (custom managers
    # aren't carried into migrations), so use the default manager and
    # include soft-deleted rows explicitly — a voided or soft-deleted
    # sale still holds a reference that must not collide later.
    for sale in Sale.objects.all().select_related("cashier__branch"):
        match = OLD_REFERENCE_RE.match(sale.reference or "")
        if not match:
            continue  # already migrated, or an unexpected format — leave alone

        year, seq = match.groups()
        code = sale.cashier.branch.code
        # queryset.update(), not instance.save() -- same reasoning as
        # auth_users.0002_branch_code: no model save() logic should run
        # against a historical model, and update() won't hard-fail the
        # whole migration if a row can't be matched.
        Sale.objects.filter(pk=sale.pk).update(reference=f"BLD-{code}-{year}-{seq}")


def strip_branch_code(apps, schema_editor):
    """
    Reverse: BLD-BUE-2026-0001 -> BLD-2026-0001.

    Only safe on a single-branch install; with several branches this
    would reintroduce exactly the collisions §8.1 exists to prevent, so
    it raises rather than silently corrupting data.
    """
    Sale = apps.get_model("sales", "Sale")
    Branch = apps.get_model("auth_users", "Branch")

    if Branch.objects.count() > 1:
        raise RuntimeError(
            "Cannot reverse this migration with more than one branch — "
            "stripping branch codes would make sale references ambiguous."
        )

    new_reference_re = re.compile(r"^BLD-[A-Z0-9]+-(\d{4})-(\d+)$")
    for sale in Sale.objects.all():
        match = new_reference_re.match(sale.reference or "")
        if not match:
            continue
        year, seq = match.groups()
        Sale.objects.filter(pk=sale.pk).update(reference=f"BLD-{year}-{seq}")


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
        # Branch.code must exist and be populated before references can
        # embed it.
        ("auth_users", "0002_branch_code"),
    ]

    operations = [
        migrations.RunPython(add_branch_code, strip_branch_code),
    ]
