# Negotiated-pricing bounds on Category and Product (Phase 2 §3.1).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_backfill_average_cost'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='discount_floor_pct',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='category',
            name='surplus_ceiling_pct',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='discount_floor_pct',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='surplus_ceiling_pct',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
