"""
Single write path into the outbox, so any app can add one line to its
own atomic transaction rather than reimplementing the outbox row shape.

Wired into: sales (Sale create/void), suppliers (Purchase,
PurchasePayment), inventory (Category, Product create/edit/deactivate,
StockAdjustment, BranchPriceOverride).

What syncs and what doesn't is declared in registry.py, not decided
here — see that module for why exclusion is explicit.
"""
import datetime
import decimal
import uuid

from .models import OutboxEntry
from .registry import schema_version_for


def write_outbox_entry(*, instance, operation, branch_id=None):
    """
    Call inside the same transaction as the write to `instance`.

    `instance` must have a UUID `id`. `branch_id` defaults to
    `instance.branch_id` (every BaseModel has one); pass explicitly for
    models that don't.

    Returns the created OutboxEntry, or None if the table is registered
    as never-synced — callers don't need to check the registry
    themselves, they can call this unconditionally.
    """
    table_name = instance._meta.db_table

    # Raises UnregisteredTableError for a table nobody has classified,
    # which is deliberate: a new model should fail loudly here rather
    # than silently never reaching the cloud.
    version = schema_version_for(table_name)
    if version is None:
        return None

    if branch_id is None:
        branch_id = getattr(instance, "branch_id", None)

    return OutboxEntry.objects.create(
        table_name=table_name,
        record_id=instance.id,
        operation=operation,
        payload=serialize_instance(instance),
        schema_version=version,
        branch_id=branch_id,
    )


def serialize_instance(instance):
    """
    JSON-safe snapshot of every concrete field on `instance`.

    Replaces the previous "str() anything non-primitive" approach, which
    produced values the cloud could not reliably reconstruct: a UUID, a
    date, and a foreign key all arrived as strings of differing shape
    with no way to tell them apart (Phase 2 design §8.3).

    Rules, applied per field type rather than per value, so the output
    shape is a property of the model and not of the particular row:

      UUID / FK to a UUID pk  ->  canonical UUID string
      datetime                ->  ISO 8601, always UTC, 'Z'-suffixed
      date                    ->  ISO 8601 date
      Decimal                 ->  string (never float — no binary
                                  rounding on money-adjacent values)
      int / float / bool      ->  as-is
      None                    ->  null
      everything else         ->  str()

    Foreign keys are serialized from `attname` (e.g. `product_id`), so a
    payload never triggers a database query to follow a relation, and
    never embeds a nested object the cloud would have to unpack.
    """
    data = {}

    for field in instance._meta.concrete_fields:
        # attname is the column-level name: `product_id` for an FK,
        # `name` for a plain field. Reading it avoids lazy-loading the
        # related object.
        value = getattr(instance, field.attname)
        data[field.attname] = _to_json_safe(value)

    return data


def _to_json_safe(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, uuid.UUID):
        return str(value)

    if isinstance(value, datetime.datetime):
        # Normalise to UTC before formatting. Branch devices run in
        # Africa/Douala and their clocks are not authoritative; storing
        # an unambiguous instant means the cloud never has to guess a
        # timezone when ordering events.
        if value.tzinfo is not None:
            value = value.astimezone(datetime.timezone.utc)
        return value.isoformat().replace("+00:00", "Z")

    if isinstance(value, datetime.date):
        return value.isoformat()

    if isinstance(value, decimal.Decimal):
        # Money in Bledger is always integer XAF, so this should not
        # occur for monetary fields — but a Decimal reaching JSON as a
        # float would silently lose precision, so it goes as a string.
        return str(value)

    return str(value)
