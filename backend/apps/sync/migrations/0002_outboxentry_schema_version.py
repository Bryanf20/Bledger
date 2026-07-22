"""
Adds OutboxEntry.schema_version (Phase 2 design §8.3).

Existing rows default to 1, which is correct: every table's contract is
at version 1 at the time this migration lands, so entries queued before
it are indistinguishable from entries queued after.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sync", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="outboxentry",
            name="schema_version",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
