# PurchaseLineItem.product_name snapshot (Phase 2 §7A.1).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0002_purchasepayment'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaselineitem',
            name='product_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
    ]
