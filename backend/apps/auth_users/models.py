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
import re
import secrets
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Group, Permission, PermissionsMixin
from django.db import models

# Fallback when a name yields no usable letters (e.g. a purely numeric
# or non-Latin business name) -- "HQ" matches the historical default
# BRANCH_ID, so a single-install shop keeps a familiar-looking code.
DEFAULT_BRANCH_CODE = "HQ"


def derive_branch_code(*names, taken=()):
    """
    Best-effort short code from a branch/business name, for standalone
    installs where no cloud is present to assign one (Phase 2 design
    §8.1 / §2.3 -- connected mode assigns codes at enrolment instead).

    Tries each name in order, taking the first 3 letters of the first
    word ("Buea Main Branch" -> "BUE"). Falls back to DEFAULT_BRANCH_CODE,
    then appends a numeric suffix until the result isn't in `taken`.
    Uniqueness matters because Branch.code is unique -- setup would
    otherwise fail on the second branch with a similar name.
    """
    candidate = ""
    for name in names:
        letters = re.sub(r"[^A-Za-z]", "", name or "")
        if letters:
            candidate = letters[:3].upper()
            break
    candidate = candidate or DEFAULT_BRANCH_CODE

    taken = {c.upper() for c in taken}
    if candidate not in taken:
        return candidate

    # Suffix until free. max_length=8 leaves ample room.
    for suffix in range(2, 1000):
        attempt = f"{candidate}{suffix}"
        if attempt not in taken:
            return attempt
    raise ValueError("Could not derive a unique branch code.")


def generate_sync_token():
    """
    A long-lived, unguessable device sync token (Phase 2 design §2.4).

    Issued by the cloud at enrolment and stored on the branch's local
    Branch row (write-only); it authenticates this device's push/pull
    calls with no user logged in. token_urlsafe(32) yields ~43 URL-safe
    chars, comfortably inside Branch.sync_token's max_length=64.
    """
    return secrets.token_urlsafe(32)


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

    # Short uppercase branch discriminator (e.g. "BUE", "DLA"), embedded
    # in every Sale.reference as BLD-<code>-<year>-<seq> (Phase 2 design
    # §8.1). Without it, two branches independently generate
    # BLD-2026-0001 and collide in the shared cloud database, where the
    # second branch's push would be permanently rejected.
    #
    # Unique so no two branches can claim the same discriminator. In
    # Phase 2 connected mode this is assigned by the cloud at enrolment;
    # in standalone it's derived from the branch/business name at setup
    # (see derive_branch_code()) and only ever seen by one install.
    code = models.CharField(
        max_length=8,
        unique=True,
        help_text="Short uppercase code used in sale references, e.g. BUE.",
    )

    deployment_mode = models.CharField(
        max_length=16, choices=DEPLOYMENT_MODE_CHOICES, default=DEPLOYMENT_STANDALONE
    )

    # Set True the moment the first-run wizard completes (design doc
    # E.6 — GET /setup/status/ gates all frontend routing on this).
    setup_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------
    # Phase 2 (Stage 3, step 9) — cloud identity & enrolment (§2.3).
    # Every field below defaults to the standalone "not enrolled" state,
    # so Phase 1 single-shop installs are completely unaffected: they
    # never set cloud_id/sync_token and keep using settings.BRANCH_ID.
    # ------------------------------------------------------------------

    # True for the head-office branch. HQ owns the catalogue and may
    # still run a till (open decision §10.2, resolved this session: HQ is
    # a sellable branch, not a pure console).
    is_hq = models.BooleanField(default=False)

    # Canonical branch identity assigned by the cloud at enrolment. Once
    # set, DeploymentContextMiddleware stamps THIS (not settings.BRANCH_ID)
    # onto every request, so records this device creates carry the id the
    # cloud agreed on. NULL until enrolled. Unique so two devices cannot
    # claim the same cloud identity locally.
    cloud_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Canonical branch_id issued by the cloud at enrolment.",
    )

    # Long-lived device credential authenticating this device's pushes /
    # pulls to the cloud (§2.4 — sync must work with nobody logged in, so
    # it is a device token, not a user token). Write-only: never appears
    # in any serializer's field list. On the cloud side it identifies the
    # calling device (see DeviceSyncTokenAuthentication).
    sync_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        help_text="Device sync token (write-only).",
    )

    # Last time this device completed a sync cycle; surfaced later by the
    # connectivity UX (§2.6) and the HQ per-branch last-seen view.
    last_synced_at = models.DateTimeField(null=True, blank=True)

    # HQ can deactivate a branch (lost device, closed shop) so its token
    # stops authenticating, without deleting historical records.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["business_name"]

    def __str__(self):
        return self.branch_name or self.business_name


class BusinessSettings(models.Model):
    """
    Business-wide policy defaults — a single row per install (Phase 2
    design §7.2). Deliberately kept separate from Branch: Branch is
    *identity* (who and where this branch is), BusinessSettings is
    *policy* (how the business chooses to operate). Once multi-branch is
    live, policy is HQ-owned and pushed to branches read-only, while each
    branch keeps its own identity — conflating the two onto Branch would
    make that split impossible later.

    Most fields here are consumed by workstreams not yet built (negotiated
    pricing, customer credit, cost/margin alerts). They live here now,
    with safe defaults, so those workstreams need no migration and no new
    settings home when they land — the same "prepare the data model early"
    approach SaleLineItem's variance fields already use.

    Singleton: exactly one row, pk pinned to 1. Not a BaseModel — there's
    nothing branch-scoped or soft-deletable about it, and it is never
    branch->cloud replicated (see apps.sync.registry.NEVER_SYNCED).
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    # --- Negotiated pricing defaults (workstream B, not yet built) ------
    # Whole-percent bounds on how far a cashier may move a price from
    # catalogue before manager approval is required. Business-wide
    # fallback; per-product/per-category overrides come later (§3.1).
    default_discount_floor_pct = models.PositiveIntegerField(
        default=0,
        help_text="Max discount %% a cashier may give without approval. 0 = no discount allowed by default.",
    )
    default_surplus_ceiling_pct = models.PositiveIntegerField(
        default=0,
        help_text="Max surplus %% a cashier may add without approval. 0 = no surplus allowed by default.",
    )

    # --- Multi-branch price-deviation alert (workstream A, §9.3) --------
    price_deviation_alert_pct = models.PositiveIntegerField(
        default=20,
        help_text="HQ flags a branch price override deviating from catalogue by more than this %%.",
    )

    # --- Customer credit defaults (workstream C, not yet built) ---------
    default_credit_limit = models.PositiveIntegerField(
        default=0,
        help_text="Default customer credit limit in XAF. 0 = credit off by default.",
    )

    # --- Cost/margin alerts (workstream G, not yet built) ---------------
    margin_alert_pct = models.PositiveIntegerField(
        default=15,
        help_text="Flag a product whose average cost rose by more than this %% without a price change.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Business settings"
        verbose_name_plural = "Business settings"

    def __str__(self):
        return "Business settings"

    def save(self, *args, **kwargs):
        # Pin every write to the single row — makes accidental creation of
        # a second settings row impossible even via the ORM directly.
        self.pk = 1
        # A freshly-constructed instance (_state.adding) whose row already
        # exists would otherwise issue a second INSERT and hit the pk
        # UNIQUE constraint. Switch it to an UPDATE so it overwrites the
        # singleton instead — the whole point of a singleton is that the
        # last write wins on the one row, never errors.
        if self._state.adding and type(self).objects.filter(pk=1).exists():
            kwargs.pop("force_insert", None)
            kwargs["force_update"] = True
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """The one settings row, created with defaults on first access."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


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
                defaults={
                    "deployment_mode": Branch.DEPLOYMENT_STANDALONE,
                    # code is unique and non-nullable; derive one here so
                    # `manage.py createsuperuser` still works on a fresh
                    # install with no Branch rows.
                    "code": derive_branch_code(
                        "Default Business",
                        taken=Branch.objects.values_list("code", flat=True),
                    ),
                },
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
    