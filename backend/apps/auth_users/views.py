"""
Auth & first-run setup endpoints (design doc Part E.1 / E.6).
"""
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsOwner

from .models import Branch
from .serializers import (
    LoginSerializer,
    PinLoginSerializer,
    SetupSerializer,
    StaffUserCreateSerializer,
    UserProfileSerializer,
)


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
    POST /api/v1/setup/load-template/ — loads fixture data for the
    chosen product template (Provision Store / Boutique / Cosmetics /
    Electronics — design doc B.7 step 2).

    Stubbed for now: ProductTemplate and the fixture files live in the
    inventory app, which isn't built yet (next in the build order per
    the design doc). Returns 503, the same pattern used for the
    Phase-2 sync endpoints, so the route exists and the frontend can be
    wired up without waiting on this backend piece.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {"detail": "Product templates are not available until the inventory app is built."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class StaffUserCreateView(APIView):
    """
    POST /api/v1/users/ — owner creates staff accounts (cashier requires
    PIN, manager requires password).
    """

    permission_classes = [IsOwner]

    def post(self, request):
        serializer = StaffUserCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)
    