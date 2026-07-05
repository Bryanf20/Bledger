import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OutboxEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("table_name", models.CharField(db_index=True, max_length=100)),
                ("record_id", models.UUIDField(db_index=True)),
                ("operation", models.CharField(choices=[("insert", "Insert"), ("update", "Update"), ("delete", "Delete")], max_length=10)),
                ("payload", models.JSONField()),
                ("branch_id", models.CharField(db_index=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("attempted", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, null=True)),
                ("synced_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
