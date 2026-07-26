"""
Enrol THIS device with head office (Phase 2 design §2.3). Redeems a one-time
code minted by `provision_branch` on the cloud, and persists the returned
cloud identity into the local Branch row so the device can push/pull.

    python manage.py enrol_device --code ABCD2345 --cloud-url https://hq.example.com

--cloud-url defaults to settings.CLOUD_API_BASE_URL. Runs on the branch
device (SQLite, settings.branch). This is the CLI counterpart of the setup
wizard's "Connect to head office" path.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.auth_users.models import Branch


def call_enrol(cloud_url, code):
    """POST the code to the cloud's enrol endpoint; return the response dict."""
    url = cloud_url.rstrip("/") + "/api/v1/sync/enrol/"
    body = json.dumps({"code": code}).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise CommandError(f"Enrolment rejected (HTTP {exc.code}): {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CommandError(f"Could not reach the cloud at {cloud_url}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise CommandError(f"Malformed cloud response: {exc}") from None


def persist_enrolment(data):
    """
    Write the cloud identity into the local Branch row. cloud_id carries the
    canonical branch_id (DeploymentContextMiddleware stamps it on records);
    sync_token authenticates push/pull. A fresh branch device has no Branch
    row yet — enrolment IS its connected-mode setup — so create one; if a row
    already exists (re-enrolment), update it in place.
    """
    fields = {
        "cloud_id": data["branch_id"],
        "sync_token": data["sync_token"],
        "code": data.get("code") or "",
        "business_name": data.get("business_name") or "",
        "branch_name": data.get("branch_name") or "",
        "is_hq": data.get("is_hq", False),
        "deployment_mode": Branch.DEPLOYMENT_CONNECTED,
        "setup_complete": True,
        "is_active": True,
    }
    existing = Branch.objects.first()
    if existing is None:
        return Branch.objects.create(**fields)
    for k, v in fields.items():
        setattr(existing, k, v)
    existing.save()
    return existing


class Command(BaseCommand):
    help = "Enrol this device with head office using a one-time code."

    def add_arguments(self, parser):
        parser.add_argument("--code", required=True)
        parser.add_argument("--cloud-url", default="")

    def handle(self, *args, **options):
        cloud_url = options["cloud_url"] or getattr(settings, "CLOUD_API_BASE_URL", "")
        if not cloud_url:
            raise CommandError(
                "No cloud URL. Pass --cloud-url or set CLOUD_API_BASE_URL."
            )
        code = options["code"].strip().upper()

        data = call_enrol(cloud_url, code)
        branch = persist_enrolment(data)

        self.stdout.write(self.style.SUCCESS("Device enrolled with head office."))
        self.stdout.write(f"  branch_id : {branch.cloud_id}")
        self.stdout.write(f"  branch    : {branch.branch_name} ({branch.code})")
        self.stdout.write(f"  is HQ     : {branch.is_hq}")
        self.stdout.write("Sync will begin on the next cycle (manage.py sync).")
