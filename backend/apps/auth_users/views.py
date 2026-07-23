"""
Auth & first-run setup endpoints (design doc Part E.1 / E.6).
"""
import logging

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsCashierOrAbove, IsOwner
from apps.inventory.services import TemplateNotFoundError, list_templates, load_template

from .approvals import (
    clear_failures,
    is_locked_out,
    issue_approval_token,
    record_failure,
)
from .models import BledgerUser, Branch, BusinessSettings
from .serializers import (
    BranchUpdateSerializer,
    BusinessSettingsSerializer,
    LoginSerializer,
    PinLoginSerializer,
    ResetPinSerializer,
    SetupSerializer,
    StaffUserCreateSerializer,
    StaffUserListSerializer,
    StaffUserUpdateSerializer,
    UserProfileSerializer,
    VerifyPinSerializer,
)

logger = logging.getLogger("apps.auth_users")


def _token_response(user, status_code=status.HTTP_200_OK):
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {"token": token.key, "user": UserProfileSerializer(user).data},
        status=status_code,
    )


class LoginView(APIView):
    """POST /api/v1/auth/login/ — username + password (owner, manager)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        django_login(request, user)
        return _token_response(user)


class PinLoginView(APIView):
    """POST /api/v1/auth/pin-login/ — 4-digit PIN (cashier)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PinLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        django_login(request, user)
        return _token_response(user)


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — invalidate token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        django_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """
    GET /api/v1/auth/me/ — current user profile + branch config, used
    to restore session on app load.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)


class VerifyPinView(APIView):
    """
    POST /api/v1/auth/verify-pin/ — a manager authorises a cashier's
    action by entering their username + PIN (Phase 2 design §3.2). On
    success it returns a short-lived, purpose-scoped approval token that
    the cashier's in-flight sale/credit request carries as proof; the
    consuming endpoint verifies it and records the approver.

    This is an authorisation check performed INSIDE the cashier's
    session — it must never call login/logout or issue an auth token, so
    the cashier stays logged in at the till throughout. `request.user`
    (the cashier) is untouched.

    Guards, because a 4-digit PIN over an endpoint is a brute-force
    oracle:
      - the target manager account locks after FAILURE_LIMIT failures in
        a rolling window (apps.auth_users.approvals);
      - every attempt is logged (never the PIN);
      - all invalid cases return one uniform 401, so the endpoint doesn't
        reveal whether a username exists or a PIN was close.
    """

    permission_classes = [IsCashierOrAbove]

    # Uniform failure — deliberately does not distinguish "no such user",
    # "wrong PIN", and "user isn't a manager", so none of them leak.
    _INVALID = {"detail": "Invalid username or PIN, or that person can't approve this."}

    def post(self, request):
        serializer = VerifyPinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        pin = serializer.validated_data["pin"]
        purpose = serializer.validated_data["purpose"]

        if is_locked_out(username):
            logger.warning("verify-pin locked out: username=%s purpose=%s", username, purpose)
            return Response(
                {"detail": "Too many failed attempts. Try again in a few minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            approver = BledgerUser.objects.get(username=username, is_active=True)
        except BledgerUser.DoesNotExist:
            approver = None

        approved = (
            approver is not None
            and (approver.is_manager or approver.is_owner)
            and approver.check_pin(pin)
        )

        if not approved:
            record_failure(username)
            logger.warning(
                "verify-pin failed: username=%s purpose=%s by_user=%s",
                username, purpose, getattr(request.user, "username", "?"),
            )
            return Response(self._INVALID, status=status.HTTP_401_UNAUTHORIZED)

        clear_failures(username)
        logger.info(
            "verify-pin approved: approver=%s purpose=%s for_user=%s",
            approver.username, purpose, getattr(request.user, "username", "?"),
        )
        return Response(
            {
                "approved": True,
                "approver": {"id": str(approver.id), "name": approver.name, "role": approver.role},
                "approval_token": issue_approval_token(approver, purpose),
                "purpose": purpose,
            }
        )


class SetupStatusView(APIView):
    """
    GET /api/v1/setup/status/ — gates all frontend routing until
    setup_complete is true.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        is_complete = Branch.objects.filter(setup_complete=True).exists()
        return Response({"setup_complete": is_complete})


class SetupView(APIView):
    """
    POST /api/v1/setup/ — creates Branch + owner BledgerUser + logs in,
    in one call.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        if Branch.objects.filter(setup_complete=True).exists():
            return Response(
                {"detail": "Setup has already been completed on this install."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = SetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _branch, owner = serializer.save()
        django_login(request, owner)
        return _token_response(owner, status_code=status.HTTP_201_CREATED)


class LoadTemplateView(APIView):
    """
    POST /api/v1/setup/load-template/
    Body: {"template_key": "provision-store"}

    Owner-only (same gate as the rest of the setup wizard — a fresh
    install only has the just-created owner authenticated at this point
    anyway). Loads the chosen ProductTemplate's categories/products onto
    request.branch_id via apps.inventory.services.load_template().
    """
    permission_classes = [IsOwner]

    def post(self, request):
        template_key = request.data.get("template_key")
        if not template_key:
            return Response({"detail": "template_key is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = load_template(template_key, request.branch_id)
        except TemplateNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(result, status=status.HTTP_201_CREATED)


class ProductTemplateListView(APIView):
    """
    GET /api/v1/setup/templates/ -- AllowAny, same reasoning as
    SetupStatusView: the wizard's step 2 must render before an owner
    account exists to authenticate as. Read-only counterpart to
    LoadTemplateView below -- returns every ProductTemplate's static
    fields plus live counts/preview names computed from its fixture
    file, not hardcoded anywhere.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(list_templates())


class StaffUserListCreateView(APIView):
    """
    GET  /api/v1/users/ — owner lists staff for their branch.
    POST /api/v1/users/ — owner creates a staff account (cashier requires
                          PIN, manager requires password).

    List is scoped to the caller's own branch: an owner manages their own
    branch's staff, not other branches' (feasibility §6 — user accounts
    are per-branch even though HQ-owned in connected mode).
    """

    permission_classes = [IsOwner]

    def get(self, request):
        staff = BledgerUser.objects.filter(branch=request.user.branch).order_by("name")
        return Response(StaffUserListSerializer(staff, many=True).data)

    def post(self, request):
        serializer = StaffUserCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class StaffUserDetailView(APIView):
    """
    GET   /api/v1/users/{id}/ — one staff member.
    PATCH /api/v1/users/{id}/ — edit name / role / is_active.

    Deactivation is PATCH is_active=false (users are never deleted — sale
    and adjustment history references them). Two lockout guards live here
    rather than in the serializer, because only the view knows who the
    caller is:
      1. An owner can't deactivate or demote themselves — that could
         leave the business with no owner and no way back in.
      2. Only the caller's own branch's staff are reachable.
    """

    permission_classes = [IsOwner]

    def _get_user(self, request, pk):
        return get_object_or_404(BledgerUser, pk=pk, branch=request.user.branch)

    def get(self, request, pk):
        user = self._get_user(request, pk)
        return Response(StaffUserListSerializer(user).data)

    def patch(self, request, pk):
        user = self._get_user(request, pk)
        is_self = user.pk == request.user.pk

        serializer = StaffUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if is_self:
            new_active = serializer.validated_data.get("is_active", user.is_active)
            new_role = serializer.validated_data.get("role", user.role)
            if not new_active:
                raise _conflict("You can't deactivate your own account.")
            if user.is_owner and new_role != BledgerUser.ROLE_OWNER:
                raise _conflict("You can't change your own owner role.")

        serializer.save()
        return Response(StaffUserListSerializer(user).data)


class StaffUserResetPinView(APIView):
    """
    POST /api/v1/users/{id}/reset-pin/ — owner sets a new 4-digit PIN for
    a staff member. Separate action from PATCH because it writes a
    credential, not a profile field (see ResetPinSerializer).
    """

    permission_classes = [IsOwner]

    def post(self, request, pk):
        user = get_object_or_404(BledgerUser, pk=pk, branch=request.user.branch)
        serializer = ResetPinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_pin(serializer.validated_data["pin"])
        user.save(update_fields=["pin_hash", "updated_at"])
        return Response(StaffUserListSerializer(user).data)


class SettingsBusinessView(APIView):
    """
    GET/PATCH /api/v1/settings/business/ — the owner edits their business
    and branch details (Phase 2 design §7.2). Operates on the caller's
    own Branch; there is exactly one in standalone mode.
    """

    permission_classes = [IsOwner]

    def get(self, request):
        return Response(BranchUpdateSerializer(request.user.branch).data)

    def patch(self, request):
        serializer = BranchUpdateSerializer(
            request.user.branch, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BusinessSettingsView(APIView):
    """
    GET/PATCH /api/v1/settings/preferences/ — business-wide policy
    defaults (Phase 2 design §7.2). Owner-only. The single settings row
    is created with defaults on first access.
    """

    permission_classes = [IsOwner]

    def get(self, request):
        return Response(BusinessSettingsSerializer(BusinessSettings.load()).data)

    def patch(self, request):
        serializer = BusinessSettingsSerializer(
            BusinessSettings.load(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def _conflict(message):
    """A 409 raised as an exception, so guard checks can early-return."""
    from rest_framework.exceptions import APIException

    class _Conflict(APIException):
        status_code = status.HTTP_409_CONFLICT
        default_detail = message

    return _Conflict(message)
    