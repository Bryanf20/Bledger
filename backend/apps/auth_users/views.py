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
from apps.inventory.services import TemplateNotFoundError, list_templates, load_template

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
    