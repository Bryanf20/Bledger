"""
Device-side enrolment helpers (Phase 2 design §2.3), shared by the
`enrol_device` management command and the setup-wizard connect endpoint.
Redeem a one-time code against the cloud and persist the returned identity
into the local Branch row.
"""
import json
import urllib.error
import urllib.request

from apps.auth_users.models import Branch


class EnrolmentError(Exception):
    """Enrolment couldn't complete (bad code, cloud unreachable, etc.)."""


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
        raise EnrolmentError(f"Enrolment rejected (HTTP {exc.code}): {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EnrolmentError(f"Could not reach the cloud at {cloud_url}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise EnrolmentError(f"Malformed cloud response: {exc}") from None


def persist_enrolment(data):
    """
    Write the cloud identity into the local Branch row. The device's Branch
    primary key is set to the cloud branch_id so pulled records that reference
    the branch (e.g. BledgerUser.branch_id) resolve locally; cloud_id mirrors
    it and is what DeploymentContextMiddleware keys on. A fresh branch device
    has no Branch row yet — enrolment IS its connected-mode setup — so create
    one; a re-enrol updates in place.
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
        return Branch.objects.create(id=data["branch_id"], **fields)
    for k, v in fields.items():
        setattr(existing, k, v)
    existing.save()
    return existing
