"""Durable account-security stop. Clearing it never logs in, sends, or passes a gate."""

import time
from uuid import uuid4

from wechat_reply_agent.adapters.wechat.base import AdapterError


def stop_path(settings):
    return settings.data_dir / "macos/security-stop.json"


def security_stopped(settings):
    # Malformed/unknown markers also stop: they must not silently enable input.
    return stop_path(settings).exists()


def require_security_clear(settings):
    if security_stopped(settings):
        raise AdapterError("mac_account_security_stop_active")


def record_security_stop(settings):
    from wechat_reply_agent.cli import write_private

    if not security_stopped(settings):
        write_private(
            stop_path(settings),
            {
                "active": True,
                "reason": "wechat_account_security_prompt",
                "at": time.time(),
                "automatic_clear": False,
            },
        )


def clear_security_stop(settings, *, confirmed=False):
    from wechat_reply_agent.cli import write_private

    if not confirmed:
        raise AdapterError("manual_login_confirmation_required")
    path = stop_path(settings)
    if path.exists():
        # Preserve the original evidence even when the marker is not valid JSON.
        history = path.parent / "security-history" / f"{uuid4().hex}.json"
        write_private(
            history,
            {
                "previous_marker": path.read_text(encoding="utf-8"),
                "manual_login_confirmed_at": time.time(),
                "gates_unchanged": True,
            },
        )
        path.unlink()
    return {"security_stop": False, "gates_unchanged": True, "native_actions": 0}
