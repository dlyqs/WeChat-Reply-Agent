"""Mac gates are specific to this platform, client build, binding and native files."""

import hashlib
import json
import platform

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import client_version, source_identity
from wechat_reply_agent.adapters.wechat.mac_profile import REVISION
from wechat_reply_agent.adapters.wechat.mac_security import require_security_clear


def context(profile):
    version, build = client_version(profile.app_path)
    if (version, build) != (profile.wechat_version, profile.wechat_build):
        raise AdapterError("mac_client_version_changed")
    return {
        "plan_version": "v5",
        "platform": "macOS",
        "foundation": "mac_db",
        "foundation_revision": REVISION,
        "input_method": "clipboard-v1",
        "window_mode": profile.window_mode,
        "send_preflight": profile.send_preflight,
        "ui_checks_degraded": profile.send_preflight != "visual",
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
    require_security_clear(settings)
    if profile.send_preflight != "visual":
        raise AdapterError("mac_degraded_mode_requires_explicit_prototype_flag")
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
            or report.get("native_stability_verified") is not True
        ):
            raise ValueError
    except (OSError, ValueError):
        raise AdapterError(f"mac_g{gate}_matching_report_required") from None


def require_degraded_prototype(settings, profile):
    """Explicit flow-only run; does not pass or rewrite either formal gate."""
    require_security_clear(settings)
    if (
        platform.system() != "Darwin"
        or profile is None
        or profile.send_preflight != "ax-window-db"
        or profile.window_mode != "independent"
        or len(profile.contacts) != 1
        or not profile.account_confirmed
    ):
        raise AdapterError("mac_explicit_degraded_profile_required")
    context(profile)
