# Activity log: unified append-only trail of major branch events (§7C / step 8c).

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('branch_id', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('action', models.CharField(max_length=40)),
                ('summary', models.CharField(max_length=255)),
                ('is_major', models.BooleanField(default=True)),
                ('target_type', models.CharField(blank=True, default='', max_length=40)),
                ('target_id', models.CharField(blank=True, default='', max_length=64)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'abstract': False,
                'indexes': [models.Index(fields=['branch_id', '-created_at'], name='activity_ac_branch__aaaa12_idx'), models.Index(fields=['branch_id', 'is_major', '-created_at'], name='activity_ac_branch__71b44f_idx')],
            },
        ),
    ]
