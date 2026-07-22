"""
Adds Branch.code — the short discriminator embedded in every sale
reference (Phase 2 design §8.1).

Three-step because the field is unique and non-nullable: add it
nullable, populate every existing row with a derived code, then tighten
the constraint. Adding it as unique+non-null in one step would fail on
any database that already has Branch rows.
"""
import re

from django.db import migrations, models

# Deliberately inlined rather than imported from apps.auth_users.models.
# A migration is a historical record: it must keep applying identically
# years from now, even if derive_branch_code() is later changed, moved,
# or deleted. Importing live application code into a migration couples
# the past to the present and is the usual way old migrations break on
# a fresh clone. The live copy in models.py is what setup uses; this
# frozen copy is what this migration uses. They are allowed to diverge.
DEFAULT_BRANCH_CODE = "HQ"


def _derive_branch_code(*names, taken=()):
    candidate = ""
    for name in names:
        letters = re.sub(r"[^A-Za-z]", "", name or "")
        if letters:
            candidate = letters[:3].upper()
            break
    candidate = candidate or DEFAULT_BRANCH_CODE

    taken = {c.upper() for c in taken}
    if candidate not in taken:
        return candidate

    for suffix in range(2, 1000):
        attempt = f"{candidate}{suffix}"
        if attempt not in taken:
            return attempt
    raise ValueError("Could not derive a unique branch code.")


def populate_codes(apps, schema_editor):
    Branch = apps.get_model("auth_users", "Branch")

    taken = set()
    for branch in Branch.objects.all().order_by("created_at"):
        code = _derive_branch_code(branch.branch_name, branch.business_name, taken=taken)
        # queryset.update() rather than instance.save(update_fields=...):
        # save() raises "Save with update_fields did not affect any rows"
        # if the row can't be matched, which turns any data oddity into a
        # hard migration failure mid-transaction. update() is also the
        # conventional choice in a data migration — no model save() logic
        # (validation, auto_now, signals) should run against a historical
        # model.
        Branch.objects.filter(pk=branch.pk).update(code=code)
        taken.add(code)


def reverse_populate(apps, schema_editor):
    # Nothing to undo — the column itself is removed by the reverse of
    # AddField, so clearing values first would be redundant.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("auth_users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="code",
            field=models.CharField(
                max_length=8,
                null=True,
                help_text="Short uppercase code used in sale references, e.g. BUE.",
            ),
        ),
        migrations.RunPython(populate_codes, reverse_populate),
        migrations.AlterField(
            model_name="branch",
            name="code",
            field=models.CharField(
                max_length=8,
                unique=True,
                help_text="Short uppercase code used in sale references, e.g. BUE.",
            ),
        ),
    ]
