"""
Adds Product.barcode — optional scan code, unique per branch only when
set (Phase 2 design §5). The partial UniqueConstraint excludes the empty
string, so any number of products may carry no barcode.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_product_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='barcode',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True), models.Q(('barcode', ''), _negated=True)), fields=('branch_id', 'barcode'), name='unique_barcode_per_branch'),
        ),
    ]
