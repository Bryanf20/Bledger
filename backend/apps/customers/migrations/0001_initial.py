"""
Customers & credit: branch-scoped Customer + append-only CustomerPayment
(Phase 2 design §4). Balance is derived, not stored.
"""
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
            name='Customer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('branch_id', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('name', models.CharField(max_length=150)),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('area', models.CharField(blank=True, default='', max_length=150)),
                ('notes', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('credit_limit', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CustomerPayment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('branch_id', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('amount', models.PositiveIntegerField()),
                ('payment_date', models.DateField()),
                ('payment_method', models.CharField(blank=True, default='cash', max_length=20)),
                ('note', models.TextField(blank=True, default='')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='customers.customer')),
                ('recorded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_payments_recorded', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-payment_date', '-created_at'],
                'abstract': False,
            },
        ),
    ]
