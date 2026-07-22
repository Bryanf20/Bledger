"""
The single declaration of what syncs and what doesn't (Phase 2 design
§8.3, §8.4).

Two things live here because they answer the same question — "how does
the cloud understand this table?":

  SYNCED_TABLES     tables the sync engine replicates, and the payload
                    schema version each one currently emits.
  NEVER_SYNCED      tables deliberately excluded, with the reason.

Keeping exclusion *explicit* rather than implicit matters. A table that
simply isn't handled looks identical to a table someone forgot — and the
failure mode is silent (rows quietly never reach the cloud). Listing
NEVER_SYNCED lets write_outbox_entry() hard-fail on an unknown table, so
adding a model without deciding its sync status is a loud error during
development rather than missing data in production.

Table names are Django's `Model._meta.db_table`. tests/test_registry.py
asserts every name here resolves to a real model, so a typo can't sit
undetected.
"""

# Payload schema version per table. Bump when a table's serialized shape
# changes (field added, removed, or retyped) so the cloud can tell which
# contract a queued entry was written against.
#
# This is what makes upgrades survivable: a branch offline for two weeks
# pushes entries written by the *old* code, and the cloud must know that
# rather than inferring it from the payload's shape.
SYNCED_TABLES = {
    "inventory_category": 1,
    "inventory_product": 1,
    "inventory_branchpriceoverride": 1,
    "inventory_stockadjustment": 1,
    "sales_sale": 1,
    "sales_salelineitem": 1,
    "suppliers_supplier": 1,
    "suppliers_purchase": 1,
    "suppliers_purchaselineitem": 1,
    "suppliers_purchasepayment": 1,
}


NEVER_SYNCED = {
    "sales_heldsale": (
        "Transient by design — a held cart is hard-deleted on restore and "
        "is only meaningful at the till that created it. Syncing it would "
        "push a row that is then deleted with no tombstone, leaving an "
        "orphan in the cloud (Phase 2 design §8.4)."
    ),
    "auth_users_branch": (
        "Branch identity is established by enrolment (§2.3), not outbox "
        "replication — a branch pushing its own Branch row could overwrite "
        "cloud-owned identity fields."
    ),
    "auth_users_bledgeruser": (
        "User accounts are HQ-owned and flow cloud -> branch via pull, "
        "never branch -> cloud (feasibility §6)."
    ),
    "inventory_producttemplate": (
        "Global static seed data, identical on every install and created "
        "by migration. Nothing to replicate."
    ),
    "sync_outboxentry": (
        "The outbox is the sync mechanism itself. Replicating it would be "
        "infinitely recursive."
    ),
}


class UnregisteredTableError(Exception):
    """
    Raised when a write is attempted for a table in neither
    SYNCED_TABLES nor NEVER_SYNCED — i.e. a model was added without
    anyone deciding whether it should sync.
    """


def schema_version_for(table_name):
    """
    Current payload schema version for `table_name`.

    Returns None for tables explicitly excluded from sync — callers
    should skip writing an outbox entry entirely in that case. Raises
    UnregisteredTableError for tables nobody has classified.
    """
    if table_name in NEVER_SYNCED:
        return None
    try:
        return SYNCED_TABLES[table_name]
    except KeyError:
        raise UnregisteredTableError(
            f"{table_name!r} is not registered for sync. Add it to "
            f"SYNCED_TABLES (with a schema version) or NEVER_SYNCED "
            f"(with a reason) in apps/sync/registry.py."
        ) from None


def is_synced(table_name):
    return table_name in SYNCED_TABLES
