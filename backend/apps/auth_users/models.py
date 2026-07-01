"""
Branch and BledgerUser — the two models in Part D of the design doc that
deliberately do *not* inherit apps.core.models.BaseModel:

    "All Phase 1 models, excluding Branch, BledgerUser, and OutboxEntry,
    inherit BaseModel."

Branch is the root entity (business/branch config). BledgerUser extends
AbstractBaseUser directly rather than BaseModel because auth models have
their own lifecycle (password hashing, last_login, permissions) that
doesn't fit the synced-table shape (branch_id, deleted_at, synced_at,
version) BaseModel is built for.
"""
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Group, Permission, PermissionsMixin
from django.db import models


class Branch(models.Model):
    """
    Business and branch config (design doc Part D). Root entity — does
    not inherit BaseModel. In standalone mode (Phase 1) there is exactly
    one Branch per install, created atomically by the first-run wizard
    (POST /api/v1/setup/, see SetupSerializer).
    """

    DEPLOYMENT_STANDALONE = "standalone"
    DEPLOYMENT_CONNECTED = "connected"
    DEPLOYMENT_MODE_CHOICES = [
        (DEPLOYMENT_STANDALONE, "Standalone"),
        (DEPLOYMENT_CONNECTED, "Connected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    business_name = models.CharField(max_length=200)
    branch_name = models.CharField(max_length=200, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    receipt_footer = models.CharField(max_length=255, blank=True, default="")

    deployment_mode = models.CharField(
        max_length=16, choices=DEPLOYMENT_MODE_CHOICES, default=DEPLOYMENT_STANDALONE
    )

    # Set True the moment the first-run wizard completes (design doc
    # E.6 — GET /setup/status/ gates all frontend routing on this).
    setup_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["business_name"]

    def __str__(self):
        return self.branch_name or self.business_name


class BledgerUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, branch, role, password, pin, **extra_fields):
        if not username:
            raise ValueError("BledgerUser requires a username")
        if not branch:
            raise ValueError("BledgerUser requires a branch")
        if not role:
            raise ValueError("BledgerUser requires a role")

        user = self.model(username=username, branch=branch, role=role, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        if pin:
            user.set_pin(pin)

        user.save(using=self._db)
        return user

    def create_user(self, username, branch, role, password=None, pin=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, branch, role, password, pin, **extra_fields)

    def create_superuser(self, username, password=None, branch=None, **extra_fields):
        """
        Required by `manage.py createsuperuser`. Not part of the Phase 1
        product flow (owners are created via the setup wizard), but kept
        so the scaffold stays a normal, runnable Django project — e.g.
        for inspecting data via /admin/ during development.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("name", username)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        if branch is None:
            branch, _ = Branch.objects.get_or_create(
                business_name="Default Business",
                defaults={"deployment_mode": Branch.DEPLOYMENT_STANDALONE},
            )

        return self._create_user(
            username, branch, BledgerUser.ROLE_OWNER, password, None, **extra_fields
        )


class BledgerUser(AbstractBaseUser, PermissionsMixin):
    """
    Auth: branch (FK), name, username, password, pin_hash, role
    (owner/manager/cashier), is_active. Extends AbstractBaseUser
    (design doc Part D).

    PermissionsMixin is included only so /admin/ keeps working once this
    becomes AUTH_USER_MODEL — Bledger's own authorization is role-based
    (apps.core.permissions), not Django's groups/permissions system.
    """

    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_CASHIER = "cashier"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_CASHIER, "Cashier"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="users")

    # Display name — distinct from the login username (e.g. "Ambe J."
    # shown in the topbar across the screens, vs the username typed at
    # login).
    name = models.CharField(max_length=150)
    username = models.CharField(max_length=150, unique=True)

    role = models.CharField(max_length=16, choices=ROLE_CHOICES)

    # Hashed with Django's password hasher (never stored/compared in
    # plaintext) — separate from `password` so a cashier's PIN and an
    # owner/manager's password are independent credentials. Optional
    # for every role: required at account-creation time for cashiers,
    # optional "mobile quick access" for manager/owner (setup wizard
    # step 3, design doc B.7).
    pin_hash = models.CharField(max_length=128, blank=True, default="")

    groups = models.ManyToManyField(
        Group,
        related_name="bledgeruser_set",
        related_query_name="bledgeruser",
        blank=True,
        help_text="The groups this user belongs to.",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="bledgeruser_set",
        related_query_name="bledgeruser",
        blank=True,
        help_text="Specific permissions for this user.",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BledgerUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.role})"

    # -- PIN handling ---------------------------------------------------
    def set_pin(self, raw_pin):
        if raw_pin and not (raw_pin.isdigit() and len(raw_pin) == 4):
            raise ValueError("PIN must be exactly 4 digits")
        self.pin_hash = make_password(raw_pin) if raw_pin else ""

    def check_pin(self, raw_pin):
        if not self.pin_hash or not raw_pin:
            return False
        return check_password(raw_pin, self.pin_hash)

    @property
    def has_pin(self):
        return bool(self.pin_hash)

    # -- role helpers -----------------------------------------------------
    @property
    def is_owner(self):
        return self.role == self.ROLE_OWNER

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_cashier(self):
        return self.role == self.ROLE_CASHIER
    