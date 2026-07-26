"""
Pull HQ catalogue changes once and apply them (Phase 2 design §2.4).
Companion to sync_push; run from cron or use the combined `sync` command.
"""
from django.core.management.base import BaseCommand

from apps.sync.cloud_client import CloudClient, TransientSyncError
from apps.sync.engine import run_pull_cycle


class Command(BaseCommand):
    help = "Pull HQ catalogue changes from head office once (Phase 2 sync pull cycle)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ignore-backoff", action="store_true",
            help="Pull now even if inside the backoff window.",
        )

    def handle(self, *args, **options):
        try:
            client = CloudClient.from_settings_and_branch()
        except TransientSyncError as exc:
            self.stderr.write(str(exc))
            return
        outcome = run_pull_cycle(
            client=client, respect_backoff=not options["ignore_backoff"]
        )
        self.stdout.write(f"pull cycle: {outcome}")
