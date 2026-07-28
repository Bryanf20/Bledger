"""
Enrol THIS device with head office (Phase 2 design §2.3). Redeems a one-time
code minted by `provision_branch` on the cloud, and persists the returned
cloud identity into the local Branch row so the device can push/pull.

    python manage.py enrol_device --code ABCD2345 --cloud-url https://hq.example.com

--cloud-url defaults to settings.CLOUD_API_BASE_URL. CLI counterpart of the
setup wizard's "Connect to head office" path.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sync.enrolment import EnrolmentError, call_enrol, persist_enrolment


class Command(BaseCommand):
    help = "Enrol this device with head office using a one-time code."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True)
        parser.add_argument("--cloud-url", default="")

    def handle(self, *args, **options):
        cloud_url = options["cloud_url"] or getattr(settings, "CLOUD_API_BASE_URL", "")
        if not cloud_url:
            raise CommandError("No cloud URL. Pass --cloud-url or set CLOUD_API_BASE_URL.")
        code = options["code"].strip().upper()

        try:
            data = call_enrol(cloud_url, code)
        except EnrolmentError as exc:
            raise CommandError(str(exc)) from None
        branch = persist_enrolment(data)

        self.stdout.write(self.style.SUCCESS("Device enrolled with head office."))
        self.stdout.write(f"  branch_id : {branch.cloud_id}")
        self.stdout.write(f"  branch    : {branch.branch_name} ({branch.code})")
        self.stdout.write(f"  is HQ     : {branch.is_hq}")
        self.stdout.write("Sync will begin on the next cycle (manage.py sync).")
