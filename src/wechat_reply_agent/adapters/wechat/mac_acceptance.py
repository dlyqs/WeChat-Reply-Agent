"""Mac gates are specific to this platform, client build, binding and native files."""

import hashlib
import json
import platform

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import client_version, source_identity
from wechat_reply_agent.adapters.wechat.mac_profile import REVISION


def context(profile):
    version, build = client_version(profile.app_path)
    if (version, build) != (profile.wechat_version, profile.wechat_build):
        raise AdapterError("mac_client_version_changed")
    return {
        "plan_version": "v5",
        "platform": "macOS",
        "foundation": "mac_db",
        "foundation_revision": REVISION,
        "wechat_version": version,
        "wechat_build": build,
        "macos": platform.mac_ver()[0],
        "architecture": platform.machine(),
        "binding_fingerprint": profile.fingerprint(),
        "source_fingerprint": hashlib.sha256(
            json.dumps(source_identity(profile.db_root), sort_keys=True).encode()
        ).hexdigest(),
    }


def require_gate(settings, profile, gate=1):
    try:
        report = json.loads(
            (settings.data_dir / f"acceptance/mac/phase-5/g{gate}.json").read_text()
        )
        expected = context(profile)
        if (
            platform.system() != "Darwin"
            or any(report.get(k) != v for k, v in expected.items())
            or report.get(f"g{gate}") != "passed"
            or report.get("recipient_confirmed") is not True
            or report.get("fresh_messages_verified") is not True
        ):
            raise ValueError
    except (OSError, ValueError):
        raise AdapterError(f"mac_g{gate}_matching_report_required") from None
