"""
Cost basis on Product (average_cost, cost_is_set, last_cost) and the
ProductPriceHistory audit log (Phase 2 design §7A). Schema only; the
backfill of average_cost from existing purchase history is the separate
0006 data migration.
"""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_product_barcode'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='average_cost',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='product',
            name='cost_is_set',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='product',
            name='last_cost',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ProductPriceHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('branch_id', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('retail_price', models.PositiveIntegerField()),
                ('bulk_price', models.PositiveIntegerField(blank=True, null=True)),
                ('bulk_min_qty', models.PositiveIntegerField(blank=True, null=True)),
                ('changed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='price_changes', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_history', to='inventory.product')),
            ],
            options={
                'ordering': ['-created_at'],
                'abstract': False,
            },
        ),
    ]
