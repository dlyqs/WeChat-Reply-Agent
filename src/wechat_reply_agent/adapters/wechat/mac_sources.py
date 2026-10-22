"""Allow new local media shards while preserving every previously accepted DB identity."""

import hashlib
import itertools
import json
import re


def source_fingerprint(sources):
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()


def media_database(name):
    return re.fullmatch(r"(?:message|media)/media_[0-9]+\.db", name) is not None


def extends_with_media(previous, current):
    return (
        bool(previous)
        and all(current.get(k) == v for k, v in previous.items())
        and all(media_database(k) for k in current.keys() - previous.keys())
    )


def matching_accepted_sources(current, fingerprint):
    """Recover a legacy manifest from its exact hash, permitting only extra media DBs.

    Old reports store only a hash. Removing optional media entries must reproduce
    that hash exactly; replacements/deletions of any accepted entry cannot match.
    Bound the search rather than accepting an unverifiable legacy report.
    """
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        return None
    if source_fingerprint(current) == fingerprint:
        return current
    optional = [name for name in current if media_database(name)]
    if len(optional) > 12:
        return None
    for count in range(1, len(optional) + 1):
        for extra in itertools.combinations(optional, count):
            accepted = {k: v for k, v in current.items() if k not in extra}
            if accepted and source_fingerprint(accepted) == fingerprint:
                return accepted
    return None


def runtime_binding_sources(settings, profile, current):
    """Keep the accepted ledger anchor stable; live source checks still pin all DBs."""
    if profile.send_preflight != "ax-window-db":
        return current
    try:
        directory = settings.data_dir / "acceptance/mac/phase-5"
        report = json.loads((directory / "degraded-flow.json").read_text())
        fixed = json.loads((directory / "degraded-fixed-send.json").read_text())
        fingerprint = report.get("source_fingerprint")
        if fingerprint != fixed.get("source_fingerprint"):
            return current
        return matching_accepted_sources(current, fingerprint) or current
    except (OSError, ValueError, AttributeError):
        return current
