"""
Wiring around the push loop: the CloudClient bootstrap and the sync_push
management command degrade cleanly when the device isn't enrolled.
"""
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.sync.cloud_client import CloudClient, TransientSyncError


@pytest.mark.django_db
@override_settings(CLOUD_API_BASE_URL="")
def test_client_bootstrap_raises_when_not_enrolled():
    with pytest.raises(TransientSyncError):
        CloudClient.from_settings_and_branch()


@pytest.mark.django_db
@override_settings(CLOUD_API_BASE_URL="")
def test_sync_push_command_reports_and_does_not_crash():
    out, err = StringIO(), StringIO()
    call_command("sync_push", stdout=out, stderr=err)
    # No enrolment / no cloud URL: it explains itself on stderr, no traceback.
    assert "head office" in err.getvalue().lower() or "enrolled" in err.getvalue().lower()


@pytest.mark.django_db
@override_settings(CLOUD_API_BASE_URL="https://hq.example.com")
def test_client_builds_from_enrolled_branch(new_branch):
    from apps.auth_users.models import Branch

    Branch.objects.filter(pk=new_branch.pk).update(sync_token="tok-xyz")
    client = CloudClient.from_settings_and_branch()
    assert client.sync_token == "tok-xyz"
    assert client.base_url == "https://hq.example.com"
