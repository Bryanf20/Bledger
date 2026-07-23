# Sale.customer FK + credit payment method (Phase 2 §4).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
        ('sales', '0004_salelineitem_brokered'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sales', to='customers.customer'),
        ),
        migrations.AlterField(
            model_name='sale',
            name='payment_method',
            field=models.CharField(choices=[('cash', 'Cash'), ('mtn_momo', 'MTN MoMo'), ('orange_money', 'Orange Money'), ('credit', 'Credit'), ('other', 'Other')], max_length=20),
        ),
    ]
