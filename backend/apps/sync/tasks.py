"""
django.tasks binding for the push loop (Phase 2 design §2.7 — Django 6.0's
native tasks framework is the locked decision).

The task is a thin wrapper: all the work is in engine.run_push_cycle, which
is what the tests and the `sync_push` management command exercise directly.
The command (run from system cron every ~30s) is the tested, dependency-
free trigger; this @task lets a deployment instead drive the loop from a
django.tasks worker if it prefers.

django.tasks is imported defensively so this module can't break app startup
on a Django build that lacks it (e.g. a test shim); the fallback runs the
task synchronously, which is exactly the immediate-backend behaviour.
"""
try:  # Django 6.0+
    from django.tasks import task
except ImportError:  # pragma: no cover - only on older/shimmed Django
    def task(*decorator_args, **decorator_kwargs):
        def wrap(fn):
            fn.enqueue = fn  # calling .enqueue(...) just runs it inline
            return fn

        if decorator_args and callable(decorator_args[0]):
            return wrap(decorator_args[0])
        return wrap


@task
def push_outbox_task():
    """Drain the outbox once. Safe to call on every scheduler tick."""
    from .cloud_client import CloudClient, TransientSyncError
    from .engine import FAILED, run_push_cycle

    try:
        client = CloudClient.from_settings_and_branch()
    except TransientSyncError:
        # Not enrolled / no cloud URL yet — nothing to do, not an error.
        return FAILED
    return run_push_cycle(client=client)


@task
def sync_task():
    """One full push+pull cycle. Safe to call on every scheduler tick."""
    from .cloud_client import CloudClient, TransientSyncError
    from .engine import FAILED, run_sync_cycle

    try:
        client = CloudClient.from_settings_and_branch()
    except TransientSyncError:
        return FAILED, FAILED
    return run_sync_cycle(client=client)
