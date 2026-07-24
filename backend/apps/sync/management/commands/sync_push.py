"""
Run one branch push cycle (Phase 2 design §2.7). The concrete, dependency-
free trigger for the outbox drain — point system cron at it:

    * * * * *  cd /app/backend && python manage.py sync_push   # then every 30s

It self-limits via the run lock and backoff, so a too-frequent schedule is
harmless. Requires an enrolled device and CLOUD_API_BASE_URL set.
"""
from django.core.management.base import BaseCommand

from apps.sync.cloud_client import CloudClient, TransientSyncError
from apps.sync.engine import DEFAULT_BATCH_SIZE, run_push_cycle


class Command(BaseCommand):
    help = "Drain the outbox to head office once (Phase 2 sync push cycle)."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
        parser.add_argument(
            "--ignore-backoff",
            action="store_true",
            help="Push now even if inside the backoff window (manual flush).",
        )

    def handle(self, *args, **options):
        try:
            client = CloudClient.from_settings_and_branch()
        except TransientSyncError as exc:
            self.stderr.write(str(exc))
            return
        outcome = run_push_cycle(
            client=client,
            batch_size=options["batch_size"],
            respect_backoff=not options["ignore_backoff"],
        )
        self.stdout.write(f"push cycle: {outcome}")
