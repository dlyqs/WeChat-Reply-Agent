"""Windows acceptance, including identity-bound recognition of original v4 reports."""

import json
import sqlite3

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.replica_bridge import environment

REVISION = "d322c4a9b1124228820bab363e5676016f188fc6"


def require_runtime_acceptance(settings, profile, binding, gates=(1, 2)):
    try:
        env = environment()
        if env.get("platform") != "Windows" or env.get("wechat_version") != profile.wechat_version:
            raise ValueError
        for gate in gates:
            path = settings.data_dir / f"acceptance/windows/phase-{gate}/report.json"
            if not path.exists():
                path = settings.data_dir / f"acceptance/phase-{gate}/report.json"
            report = json.loads(path.read_text())
            version = report.get("wechat_version") or report.get("environment", {}).get(
                "wechat_version"
            )
            if (
                report.get(f"g{gate}") != "passed"
                or report.get("foundation") != "replica"
                or version != profile.wechat_version
                or report.get("platform", "Windows") != "Windows"
            ):
                raise ValueError
            if report.get("plan_version") == "v5":
                if (
                    report.get("foundation_revision") != REVISION
                    or report.get("binding_fingerprint") != binding.fingerprint
                ):
                    raise ValueError
            elif report.get("plan_version") == "v4":
                # Original reports need an existing, identical Phase 3 ledger binding.
                # A copied passed report without that local identity cannot authorize a run.
                path = settings.data_dir / "prototype.sqlite3"
                with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
                    old = db.execute("SELECT value FROM metadata WHERE key='binding'").fetchone()
                if not old or old[0] != binding.fingerprint:
                    raise ValueError
            else:
                raise ValueError
    except (OSError, ValueError, TypeError, AttributeError, sqlite3.Error):
        raise AdapterError("windows_matching_acceptance_required") from None
