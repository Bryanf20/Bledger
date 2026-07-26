"""
One full sync cycle — push the outbox, then pull catalogue changes (Phase 2
design §2.7). The single entrypoint to point system cron at:

    * * * * *  cd /app/backend && python manage.py sync   # and every 30s

Self-limits via the run lock and backoff, so a frequent schedule is safe.
"""
from django.core.management.base import BaseCommand

from apps.sync.cloud_client import CloudClient, TransientSyncError
from apps.sync.engine import DEFAULT_BATCH_SIZE, run_sync_cycle


class Command(BaseCommand):
    help = "Run one full push+pull sync cycle against head office (Phase 2)."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
        parser.add_argument("--ignore-backoff", action="store_true")

    def handle(self, *args, **options):
        try:
            client = CloudClient.from_settings_and_branch()
        except TransientSyncError as exc:
            self.stderr.write(str(exc))
            return
        push_outcome, pull_outcome = run_sync_cycle(
            client=client,
            batch_size=options["batch_size"],
            respect_backoff=not options["ignore_backoff"],
        )
        self.stdout.write(f"sync cycle: push={push_outcome} pull={pull_outcome}")
