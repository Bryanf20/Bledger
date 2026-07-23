# Finances & cashbook: ExpenseCategory + CashbookEntry (Phase 2 §7B.2).

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
            name='ExpenseCategory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('branch_id', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
                'constraints': [models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('branch_id', 'name'), name='unique_expense_category_per_branch')],
            },
        ),
        migrations.CreateModel(
            name='CashbookEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('branch_id', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('direction', models.CharField(choices=[('expense', 'Expense (money out)'), ('income', 'Income (money in)')], default='expense', max_length=10)),
                ('amount', models.PositiveIntegerField()),
                ('occurred_on', models.DateField()),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('payment_method', models.CharField(blank=True, default='cash', max_length=20)),
                ('recorded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cashbook_entries', to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='entries', to='finances.expensecategory')),
            ],
            options={
                'ordering': ['-occurred_on', '-created_at'],
                'abstract': False,
            },
        ),
    ]
