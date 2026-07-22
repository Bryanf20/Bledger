"""
Serializers for auth, first-run setup, and staff account creation
(design doc Part E.1 / E.6).
"""
from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework import serializers

from .models import BledgerUser, Branch, derive_branch_code


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "id",
            "business_name",
            "branch_name",
            # Exposed so the frontend can display/identify the branch a
            # sale reference belongs to without parsing the reference
            # string (Phase 2 design §8.1).
            "code",
            "address",
            "phone",
            "receipt_footer",
            "deployment_mode",
            "setup_complete",
        ]
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Used by GET /auth/me/ to restore session on app load — current user
    profile + branch config, in one response (design doc E.1).
    """

    branch = BranchSerializer(read_only=True)

    class Meta:
        model = BledgerUser
        fields = ["id", "name", "username", "role", "is_active", "has_pin", "branch"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """POST /auth/login/ — username + password (owner, manager)."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(
                "Invalid username or password.", code="authorization"
            )
        if not user.is_active:
            raise serializers.ValidationError(
                "This account has been deactivated.", code="authorization"
            )
        attrs["user"] = user
        return attrs


class PinLoginSerializer(serializers.Serializer):
    """POST /auth/pin-login/ — 4-digit PIN (cashier fast access)."""

    username = serializers.CharField()
    pin = serializers.CharField(min_length=4, max_length=4)

    def validate(self, attrs):
        # Looked up by username + checked against the hash explicitly
        # (rather than via Django's `authenticate()`) because the PIN
        # is a second, independent credential — not the account password.
        try:
            user = BledgerUser.objects.get(username=attrs["username"], is_active=True)
        except BledgerUser.DoesNotExist:
            user = None

        if user is None or not user.check_pin(attrs["pin"]):
            raise serializers.ValidationError(
                "Invalid username or PIN.", code="authorization"
            )
        attrs["user"] = user
        return attrs


class StaffUserCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/users/ — owner creates staff accounts (design doc E.6).
    Cashier accounts require a PIN; manager accounts require a password
    (and may optionally also set a PIN for mobile quick access).
    """

    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )
    pin = serializers.CharField(
        write_only=True, required=False, allow_blank=True, min_length=4, max_length=4
    )

    class Meta:
        model = BledgerUser
        fields = ["id", "name", "username", "role", "password", "pin", "is_active"]
        read_only_fields = ["id"]

    def validate_username(self, value):
        if BledgerUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def validate(self, attrs):
        role = attrs.get("role")
        password = attrs.get("password")
        pin = attrs.get("pin")

        if role == BledgerUser.ROLE_CASHIER and not pin:
            raise serializers.ValidationError(
                {"pin": "A 4-digit PIN is required for cashier accounts."}
            )
        if role in (BledgerUser.ROLE_MANAGER, BledgerUser.ROLE_OWNER) and not password:
            raise serializers.ValidationError(
                {"password": "A password is required for manager and owner accounts."}
            )
        if password and len(password) < 8:
            raise serializers.ValidationError(
                {"password": "Password must be at least 8 characters."}
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        pin = validated_data.pop("pin", None)
        branch = self.context["request"].user.branch
        return BledgerUser.objects.create_user(
            username=validated_data["username"],
            branch=branch,
            role=validated_data["role"],
            password=password or None,
            pin=pin or None,
            name=validated_data["name"],
        )


class SetupSerializer(serializers.Serializer):
    """
    POST /api/v1/setup/ — creates Branch + owner BledgerUser + logs in,
    in one call (design doc E.6). Combines wizard step 1 (Business) and
    step 3 (Account); step 2 (product template) is a separate call,
    POST /api/v1/setup/load-template/, once the inventory app exists.
    """

    # Step 1 — Business
    business_name = serializers.CharField(max_length=200)
    branch_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32)
    receipt_footer = serializers.CharField(max_length=255, required=False, allow_blank=True)

    # Step 3 — Account
    owner_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True, trim_whitespace=False)
    pin = serializers.CharField(required=False, allow_blank=True, min_length=4, max_length=4)

    def validate_username(self, value):
        if BledgerUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def create(self, validated_data):
        branch_name = validated_data.get("branch_name", "")
        # Branch.code is unique and embedded in every sale reference
        # (Phase 2 design §8.1). Standalone installs have no cloud to
        # assign one, so derive it from the branch name (falling back to
        # the business name), skipping any code already taken.
        code = derive_branch_code(
            branch_name,
            validated_data["business_name"],
            taken=Branch.objects.values_list("code", flat=True),
        )
        branch = Branch.objects.create(
            business_name=validated_data["business_name"],
            branch_name=branch_name,
            address=validated_data.get("address", ""),
            phone=validated_data["phone"],
            receipt_footer=validated_data.get("receipt_footer", ""),
            deployment_mode=getattr(settings, "DEPLOYMENT_MODE", Branch.DEPLOYMENT_STANDALONE),
            setup_complete=True,
            code=code,
        )
        owner = BledgerUser.objects.create_user(
            username=validated_data["username"],
            branch=branch,
            role=BledgerUser.ROLE_OWNER,
            password=validated_data["password"],
            pin=validated_data.get("pin") or None,
            name=validated_data["owner_name"],
        )
        return branch, owner
    