"""
Manager-approval primitive (Phase 2 design §3.2).

Two things a cashier-initiated approval needs, shared by every feature
that gates an action behind a manager's PIN (negotiated pricing beyond
the floor/ceiling, a credit sale over a customer's limit):

  1. A way to prove, later and statelessly, that a specific manager
     approved a specific *kind* of action — the approval token.
  2. Protection against the fact that a 4-digit PIN checked over an
     endpoint is a brute-force oracle — the per-account lockout.

Neither touches the caller's session: an approval is an authorisation
check performed *inside another user's session* (the cashier stays
logged in at the till), never a login.
"""
from django.core import signing
from django.core.cache import cache

# --- Approval tokens -------------------------------------------------------
#
# A token is a signed, expiring statement "manager <id> approved a
# <purpose> action". Signed (not stored) so verification needs no DB row
# and no cleanup; short-lived so a captured token can't be replayed
# minutes later; scoped by `purpose` so a token issued to approve a price
# variance can't be replayed to approve a credit override.
_APPROVAL_SALT = "bledger.auth_users.approval"

# The kinds of action a manager PIN can approve. A token is scoped to
# exactly one of these; the consuming endpoint checks its own purpose,
# so a token can't be repurposed. New approval-gated features add their
# purpose here.
PURPOSE_PRICE_VARIANCE = "price_variance"   # negotiated pricing beyond floor/ceiling (§3)
PURPOSE_CREDIT_OVERRIDE = "credit_override"  # credit sale over a customer's limit (§4)
VALID_PURPOSES = frozenset({PURPOSE_PRICE_VARIANCE, PURPOSE_CREDIT_OVERRIDE})

# Approval must be used almost immediately — it's handed straight to the
# sale/credit request the cashier is completing. Two minutes covers a
# manager walking away mid-transaction without leaving a usable token
# lying around.
APPROVAL_TOKEN_MAX_AGE_SECONDS = 120


class ApprovalError(Exception):
    """Raised when an approval token is missing, tampered, expired, or
    issued for a different purpose than the one being checked."""


def issue_approval_token(approver, purpose):
    """Signed token attesting that `approver` approved a `purpose` action."""
    return signing.dumps(
        {"approver_id": str(approver.pk), "purpose": purpose},
        salt=_APPROVAL_SALT,
    )


def verify_approval_token(token, *, purpose, max_age=APPROVAL_TOKEN_MAX_AGE_SECONDS):
    """
    Return the approver's id string if `token` is a valid, unexpired
    approval for exactly `purpose`; raise ApprovalError otherwise.

    Callers (the future sale / credit endpoints) resolve the id to a
    BledgerUser and record it as the approver.
    """
    if not token:
        raise ApprovalError("Manager approval is required for this action.")
    try:
        data = signing.loads(token, salt=_APPROVAL_SALT, max_age=max_age)
    except signing.SignatureExpired:
        raise ApprovalError("That approval has expired — ask the manager to approve again.")
    except signing.BadSignature:
        raise ApprovalError("That approval isn't valid.")

    if data.get("purpose") != purpose:
        # A token minted to approve one kind of action must not unlock a
        # different one.
        raise ApprovalError("That approval was for a different action.")
    return data["approver_id"]


# --- Brute-force lockout ---------------------------------------------------
#
# The verify-pin endpoint checks a 4-digit PIN, so the whole space is
# 10,000 guesses. We lock a *target account* after a few failures rather
# than throttling the caller, because the thing being attacked is the
# manager's PIN, not the cashier's session. Keyed per username so one
# manager being hammered can't be brute-forced, and clears on the first
# success.
FAILURE_LIMIT = 5
FAILURE_WINDOW_SECONDS = 300  # 5 minutes


def _fail_key(username):
    return f"verify_pin_fails:{(username or '').lower()}"


def is_locked_out(username):
    return (cache.get(_fail_key(username)) or 0) >= FAILURE_LIMIT


def record_failure(username):
    """
    Count one failed attempt against `username`, within a rolling window.

    Note: get-then-set is not atomic across processes; acceptable for the
    single-process standalone/branch deployment this runs in. A shared
    cache backend with atomic incr would be the upgrade if it ever runs
    multi-process.
    """
    key = _fail_key(username)
    cache.set(key, (cache.get(key) or 0) + 1, FAILURE_WINDOW_SECONDS)


def clear_failures(username):
    cache.delete(_fail_key(username))
