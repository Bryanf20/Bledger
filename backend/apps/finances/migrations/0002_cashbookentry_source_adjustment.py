# Links a damage/expiry loss expense back to the StockAdjustment that
# caused it (Phase 2 §7B.2 / step 8d) — traceability + double-book guard.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finances', '0001_initial'),
        ('inventory', '0007_pricing_bounds'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashbookentry',
            name='source_adjustment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booked_expenses', to='inventory.stockadjustment'),
        ),
    ]
