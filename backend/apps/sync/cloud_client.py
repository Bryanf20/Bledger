"""
The branch device's HTTP client to the head-office cloud (Phase 2 design
§2.4). Deliberately stdlib-only (urllib) — a branch till shouldn't pull in
a new dependency just to POST a batch a few times a minute.

Only push is here; pull (GET /sync/pull/) arrives in step 12.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class TransientSyncError(Exception):
    """
    A failure that should be retried: network down, timeout, or a 5xx from
    the cloud (Phase 2 design §2.4). The push loop increments its failure
    counter and backs off; the outbox entries stay pending. A bad device
    token (401/403) is also treated as transient — it's usually a
    misconfiguration an owner will fix, not a reason to drop writes.
    """


class CloudClient:
    def __init__(self, base_url, sync_token, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.sync_token = sync_token
        self.timeout = timeout

    @classmethod
    def from_settings_and_branch(cls):
        """
        Build from settings.CLOUD_API_BASE_URL + the enrolled branch's
        device token (read from the local Branch row, not env — §2.3).
        """
        from apps.auth_users.models import Branch

        base_url = getattr(settings, "CLOUD_API_BASE_URL", "") or ""
        branch = Branch.objects.filter(sync_token__isnull=False).exclude(
            sync_token=""
        ).first()
        token = branch.sync_token if branch else ""
        if not base_url or not token:
            raise TransientSyncError(
                "Device is not enrolled or CLOUD_API_BASE_URL is unset — "
                "cannot reach head office yet."
            )
        return cls(base_url, token)

    def push(self, entries):
        """
        POST a batch to /api/v1/sync/push/. Returns the parsed response
        dict ({results, server_time, ...}); raises TransientSyncError for
        anything retryable.
        """
        body = json.dumps({"entries": entries}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/v1/sync/push/",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"SyncToken {self.sync_token}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # 4xx/5xx. All are treated as transient for the push loop's
            # purposes: 5xx is obviously retryable, and 4xx here means a
            # protocol/auth problem an operator fixes — never a signal to
            # discard queued writes. (Per-entry `rejected` outcomes come
            # back inside a 200 body, handled by the engine, not here.)
            raise TransientSyncError(f"Cloud returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransientSyncError(f"Could not reach cloud: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise TransientSyncError(f"Malformed cloud response: {exc}") from exc

    def pull(self, since=None):
        """
        GET /api/v1/sync/pull/. `since` is the cloud clock from the last
        successful contact (server_time); omit for a full catalogue
        snapshot. Returns the parsed response dict ({records, server_time,
        count}); raises TransientSyncError for anything retryable.
        """
        url = f"{self.base_url}/api/v1/sync/pull/"
        if since:
            url += "?since=" + urllib.parse.quote(since)
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"Authorization": f"SyncToken {self.sync_token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TransientSyncError(f"Cloud returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TransientSyncError(f"Could not reach cloud: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise TransientSyncError(f"Malformed cloud response: {exc}") from exc
