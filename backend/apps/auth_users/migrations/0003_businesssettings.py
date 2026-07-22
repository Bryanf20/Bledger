"""
Creates the BusinessSettings singleton — business-wide policy defaults
(Phase 2 design §7.2). Consumed by later workstreams (negotiated
pricing, credit, margin alerts); the row is created on first access via
BusinessSettings.load().
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_users', '0002_branch_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessSettings',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('default_discount_floor_pct', models.PositiveIntegerField(default=0, help_text='Max discount %% a cashier may give without approval. 0 = no discount allowed by default.')),
                ('default_surplus_ceiling_pct', models.PositiveIntegerField(default=0, help_text='Max surplus %% a cashier may add without approval. 0 = no surplus allowed by default.')),
                ('price_deviation_alert_pct', models.PositiveIntegerField(default=20, help_text='HQ flags a branch price override deviating from catalogue by more than this %%.')),
                ('default_credit_limit', models.PositiveIntegerField(default=0, help_text='Default customer credit limit in XAF. 0 = credit off by default.')),
                ('margin_alert_pct', models.PositiveIntegerField(default=15, help_text='Flag a product whose average cost rose by more than this %% without a price change.')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Business settings',
                'verbose_name_plural': 'Business settings',
            },
        ),
    ]
