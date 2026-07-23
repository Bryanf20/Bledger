# SaleLineItem snapshots: product_name and unit_cost_at_sale (Phase 2 §7A.1/§7A.5).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_branch_scoped_references'),
    ]

    operations = [
        migrations.AddField(
            model_name='salelineitem',
            name='product_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='salelineitem',
            name='unit_cost_at_sale',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
