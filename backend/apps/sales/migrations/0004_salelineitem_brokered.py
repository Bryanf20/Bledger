# SaleLineItem brokered-sale fields: is_brokered, source_note (Phase 2 §7B.1).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0003_salelineitem_cost_snapshots'),
    ]

    operations = [
        migrations.AddField(
            model_name='salelineitem',
            name='is_brokered',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='salelineitem',
            name='source_note',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]
