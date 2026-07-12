"""
One-time backfill for purchases recorded before this session's fix --
any Purchase with amount_paid > 0 and zero rows in `payments` is
missing the PurchasePayment that should have been created alongside it
(see PurchaseSerializer.create()'s docstring). Safe to run more than
once: it only acts on purchases with an empty payments list, so
already-backfilled (or genuinely fresh, correctly-recorded) purchases
are skipped on a second run.

Usage:
    python manage.py backfill_initial_purchase_payments
    python manage.py backfill_initial_purchase_payments --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.suppliers.models import Purchase, PurchasePayment
from apps.sync.models import OutboxEntry
from apps.sync.utils import write_outbox_entry


class Command(BaseCommand):
    help = "Backfill missing initial PurchasePayment rows for purchases recorded before the payment ledger existed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be backfilled without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        candidates = (
            Purchase.objects.filter(amount_paid__gt=0)
            .exclude(id__in=PurchasePayment.objects.values("purchase_id"))
            .select_related("supplier", "recorded_by")
        )

        count = candidates.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill -- every paid purchase already has a payment record."))
            return

        self.stdout.write(f"Found {count} purchase(s) missing their initial payment record.")

        for purchase in candidates:
            self.stdout.write(
                f"  {purchase.supplier.name} — {purchase.purchase_date} — {purchase.amount_paid} XAF "
                f"({'would backfill' if dry_run else 'backfilling'})"
            )
            if dry_run:
                continue

            with transaction.atomic():
                payment = PurchasePayment.objects.create(
                    branch_id=purchase.branch_id,
                    purchase=purchase,
                    amount=purchase.amount_paid,
                    payment_date=purchase.purchase_date,
                    recorded_by=purchase.recorded_by,
                    note="Paid at time of purchase (backfilled)",
                )
                write_outbox_entry(instance=payment, operation=OutboxEntry.INSERT, branch_id=purchase.branch_id)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run -- nothing was written."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Backfilled {count} purchase(s)."))
