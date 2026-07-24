"""
Device sync-token authentication (Phase 2 design §2.4).

Sync runs with nobody logged in — the branch device pushes and pulls in
the background — so its requests can't carry a user token. Instead the
cloud issues each device a long-lived sync token at enrolment (stored on
that branch's Branch.sync_token) and the device sends it on every
sync call:

    Authorization: SyncToken <token>

This authenticator resolves that token to the calling Branch and stashes
it on request.auth. The token is issued in step 9; its consumers — the
push/pull endpoints and an IsEnrolledDevice permission — arrive in step
10, so nothing is wired to it yet beyond its own tests.
"""
from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication, exceptions


class DeviceSyncTokenAuthentication(authentication.BaseAuthentication):
    keyword = "SyncToken"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            # Not a sync-token request — let other authenticators try.
            return None
        if len(header) == 1:
            raise exceptions.AuthenticationFailed(
                "Invalid sync token header: no credentials provided."
            )
        if len(header) > 2:
            raise exceptions.AuthenticationFailed(
                "Invalid sync token header: token must not contain spaces."
            )

        try:
            token = header[1].decode()
        except UnicodeError:
            raise exceptions.AuthenticationFailed(
                "Invalid sync token header: not valid utf-8."
            )

        from apps.auth_users.models import Branch

        try:
            branch = Branch.objects.get(sync_token=token)
        except Branch.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid or unknown sync token.")

        if not branch.is_active:
            # HQ has deactivated this branch (lost device, closed shop) —
            # the token stops authenticating without deleting any records.
            raise exceptions.AuthenticationFailed("This branch has been deactivated.")

        # Sync is user-less: the "user" is anonymous, and the authenticated
        # principal we care about — the Branch — travels on request.auth.
        request.enrolled_branch = branch
        return (AnonymousUser(), branch)

    def authenticate_header(self, request):
        return self.keyword
