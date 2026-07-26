"""
Provision a branch on the CLOUD and print a one-time enrolment code
(Phase 2 design §2.3). Run this on the head-office/cloud instance; hand the
printed code to whoever is setting up the new branch device, who redeems it
with `manage.py enrol_device` (or, later, the setup wizard's "Connect to
head office" path).

    python manage.py provision_branch --branch-name "Limbe Branch" --code LMB
    python manage.py provision_branch --branch-name "Head Office" --hq

This is the CLI equivalent of the owner-only POST /sync/branches/ endpoint —
the operable path until the HQ branch-management screen exists.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.auth_users.models import Branch, derive_branch_code
from apps.sync.models import EnrolmentCode


class Command(BaseCommand):
    help = "Provision a cloud branch and print a one-time enrolment code."

    def add_arguments(self, parser):
        parser.add_argument("--branch-name", required=True)
        parser.add_argument("--code", default="", help="Short branch code; derived if omitted.")
        parser.add_argument("--business-name", default="", help="Defaults to HQ's business name.")
        parser.add_argument("--hq", action="store_true", help="Mark this branch as head office.")

    def handle(self, *args, **options):
        branch_name = options["branch_name"]
        hq = Branch.objects.filter(is_hq=True).first() or Branch.objects.first()
        business_name = (
            options["business_name"]
            or getattr(hq, "business_name", "")
            or branch_name
        )

        code = options["code"].strip().upper() or derive_branch_code(
            branch_name, business_name, taken=Branch.objects.values_list("code", flat=True)
        )
        if Branch.objects.filter(code=code).exists():
            raise CommandError(f"Branch code {code!r} is already taken.")

        branch = Branch.objects.create(
            business_name=business_name,
            branch_name=branch_name,
            code=code,
            is_hq=options["hq"],
            deployment_mode=Branch.DEPLOYMENT_CONNECTED,
            setup_complete=False,
            is_active=True,
        )
        enrolment = EnrolmentCode.objects.create(branch=branch)

        self.stdout.write(self.style.SUCCESS("Branch provisioned."))
        self.stdout.write(f"  branch_id       : {branch.id}")
        self.stdout.write(f"  branch name     : {branch.branch_name}")
        self.stdout.write(f"  code            : {branch.code}")
        self.stdout.write(f"  is HQ           : {branch.is_hq}")
        self.stdout.write(self.style.WARNING(f"  ENROLMENT CODE  : {enrolment.code}"))
        self.stdout.write(f"  expires at      : {enrolment.expires_at:%Y-%m-%d %H:%M %Z}")
        self.stdout.write("Run on the new device:  python manage.py enrol_device --code " + enrolment.code)
