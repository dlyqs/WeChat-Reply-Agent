"""Remove expired Replica cache files only during an explicit, stopped-to-start transition."""

import time


def prune_replica_cache(data_dir, days):
    base = data_dir.resolve()
    cache = base / "replica"
    if not cache.exists() or not cache.resolve().is_relative_to(base):
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for path in cache.rglob("*"):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.name != "database-identities.json"
            and path.resolve().is_relative_to(cache)
            and path.stat().st_mtime < cutoff
        ):
            path.unlink()
            removed += 1
    return removed


def prune_mac_cache(data_dir, days):
    """Prune diagnostics only; keys, bootstrap state and send journals are never pruned."""
    base = data_dir.resolve()
    cache = base / "macos/diagnostics"
    if not cache.is_dir() or cache.is_symlink() or not cache.resolve().is_relative_to(base):
        return 0
    removed = 0
    for path in cache.rglob("*"):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(cache)
            and path.stat().st_mtime < time.time() - days * 86400
        ):
            path.unlink()
            removed += 1
    return removed
