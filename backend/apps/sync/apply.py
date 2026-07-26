"""
Applying a pushed outbox entry to the cloud database (Phase 2 design §2.4,
§2.5). This is the inverse of apps.sync.utils.serialize_instance: given a
branch's full-snapshot payload, reconstruct the row on the cloud.

Design decisions baked in here:

* **Idempotent.** Each apply first claims an AppliedEntry for
  (branch_id, outbox_id) in the same transaction; a re-push finds the row
  already there and is reported `duplicate` without touching the target
  table (§2.4).

* **Upsert by primary key.** insert/update/delete all carry a complete
  snapshot, so every operation is applied as "make the row equal this
  payload". A DELETE is just a snapshot whose deleted_at is set — the
  soft-delete tombstone (§2.5, feasibility delta-sync).

* **version is preserved, never bumped.** BaseModel.save() increments
  version on update; that's optimistic-concurrency bookkeeping for local
  writes. A pushed record must keep the branch's own version, so existing
  rows are written with QuerySet.update() (which bypasses save()) and new
  rows are inserted while _state.adding is True (no increment).

* **Permanent failures raise EntryRejected.** Unknown/never-synced table,
  bad foreign key, missing NOT NULL column — these will never succeed on
  retry, so the branch must stop retrying and surface them (§2.4
  `rejected`). Genuinely transient failures (DB unavailable) are NOT
  caught here; they propagate and fail the whole request so the branch
  retries the batch.
"""
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import AppliedEntry
from .registry import NEVER_SYNCED, UnregisteredTableError, schema_version_for

APPLIED = "applied"
DUPLICATE = "duplicate"
REJECTED = "rejected"

# HQ-owned catalogue tables: they flow cloud -> branch via pull only
# (Phase 2 design §2.5, "Catalogue is HQ-owned; branches may only add
# BranchPriceOverride"). A branch must never push them back, so a push of
# one is permanently rejected. BranchPriceOverride is a separate,
# branch-owned table and is unaffected.
PULL_ONLY_TABLES = {"inventory_category", "inventory_product"}


class EntryRejected(Exception):
    """A permanently invalid entry — recorded and never retried (§2.4)."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# table_name -> model, built once. Rebuilt lazily if a name is missing so
# tests that register new models don't see a stale cache.
_MODEL_BY_TABLE = {}


def _model_for_table(table_name):
    if table_name in NEVER_SYNCED:
        raise EntryRejected(f"Table {table_name!r} is excluded from sync.")

    # UnregisteredTableError => a table nobody classified; permanent.
    try:
        schema_version_for(table_name)
    except UnregisteredTableError as exc:
        raise EntryRejected(str(exc)) from None

    model = _MODEL_BY_TABLE.get(table_name)
    if model is None:
        _MODEL_BY_TABLE.clear()
        for m in django_apps.get_models():
            _MODEL_BY_TABLE[m._meta.db_table] = m
        model = _MODEL_BY_TABLE.get(table_name)
    if model is None:
        raise EntryRejected(f"No model maps to table {table_name!r}.")
    return model


def _coerce(field, value):
    """Turn a JSON-safe payload value back into what the field stores."""
    if value is None:
        return None
    # Datetimes arrive as ISO 8601 with a 'Z' suffix (see
    # serialize_instance); normalise to an offset Django's parser accepts.
    if field.get_internal_type() == "DateTimeField" and isinstance(value, str):
        value = value.replace("Z", "+00:00")
    try:
        return field.to_python(value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise EntryRejected(
            f"Bad value for {field.attname!r}: {value!r} ({exc})"
        ) from None


def deserialize_payload(model, payload):
    """
    Reverse of serialize_instance: {attname: json_value} -> (pk, field_map).

    Foreign keys are written straight from their `<field>_id` attname —
    the raw related pk, no object fetch. Payload keys the model no longer
    has are ignored (forward-compatible across a schema bump); a payload
    missing a required column simply fails at write time as an
    IntegrityError, which is reported `rejected`.
    """
    if "id" not in payload or payload["id"] is None:
        raise EntryRejected("Payload has no primary key.")

    pk = None
    field_map = {}
    for field in model._meta.concrete_fields:
        attname = field.attname
        if attname not in payload:
            continue
        value = payload[attname]
        if field.is_relation and field.many_to_one:
            # Store the raw related id; do not resolve the object.
            coerced = value
        elif field.primary_key:
            coerced = _coerce(field, value)
        else:
            coerced = _coerce(field, value)
        if field.primary_key:
            pk = coerced
        else:
            field_map[attname] = coerced
    if pk is None:
        raise EntryRejected("Payload has no primary key.")
    return pk, field_map


def _upsert(model, pk, field_map):
    """Make the row equal the payload, without bumping BaseModel.version."""
    updated = model.all_objects.filter(pk=pk).update(**field_map)
    if updated:
        return
    # No existing row — insert. _state.adding stays True through this
    # save(), so BaseModel.save() does not increment version.
    instance = model()
    instance.pk = pk
    for attname, value in field_map.items():
        setattr(instance, attname, value)
    try:
        instance.save(force_insert=True)
    except IntegrityError as exc:
        raise EntryRejected(f"Integrity error inserting {model._meta.db_table}: {exc}") from None


def apply_payload(table_name, payload):
    """
    Resolve `table_name` to a model, deserialize `payload`, and upsert the
    row. The shared core of both directions: push (branch -> cloud, wrapped
    below with idempotency and ownership guards) and pull (cloud -> branch,
    which calls this directly — pulls are naturally idempotent, a re-applied
    row being a no-op upsert). Raises EntryRejected for permanent failures.
    """
    model = _model_for_table(table_name)
    pk, field_map = deserialize_payload(model, payload)
    _upsert(model, pk, field_map)


def apply_entry(*, branch_id, entry):
    """
    Apply one pushed entry for `branch_id`. `entry` is a validated dict:
    outbox_id, table_name, record_id, operation, payload (, schema_version).

    Returns "applied" or "duplicate". Raises EntryRejected for permanent
    failures. Runs in its own transaction so one entry's outcome never
    rolls back another's.
    """
    outbox_id = entry["outbox_id"]
    table_name = entry["table_name"]
    payload = entry["payload"]

    # Guard: a device may only push records stamped with its own identity.
    payload_branch = payload.get("branch_id")
    if payload_branch is not None and str(payload_branch) != str(branch_id):
        raise EntryRejected(
            f"Payload branch_id {payload_branch!r} does not match the "
            f"authenticated branch {branch_id!r}."
        )

    # Guard: HQ-owned catalogue is pull-only; a branch may not push it (§2.5).
    if table_name in PULL_ONLY_TABLES:
        raise EntryRejected(
            f"{table_name} is HQ-owned catalogue and flows cloud -> branch "
            f"only; a branch may not push it (§2.5)."
        )

    try:
        with transaction.atomic():
            _, created = AppliedEntry.objects.get_or_create(
                branch_id=str(branch_id),
                outbox_id=outbox_id,
                defaults={
                    "table_name": table_name,
                    "record_id": entry["record_id"],
                    "operation": entry["operation"],
                },
            )
            if not created:
                return DUPLICATE

            apply_payload(table_name, payload)
    except IntegrityError as exc:
        # Bad FK or constraint violation from the apply — permanent.
        raise EntryRejected(f"Integrity error: {exc}") from None

    return APPLIED
