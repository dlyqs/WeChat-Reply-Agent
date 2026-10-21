import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import SendIntent


def intent(adapter):
    return SendIntent(
        conversation=adapter.resolve_conversation("a"), reply_text="固定测试回复", mode="live"
    )


def test_unique_local_identity(adapter):
    ref = adapter.resolve_conversation("a")
    assert ref.conversation_id == "c-a" and ref.confidence == 1
    assert "not wxid" in ref.identity_basis


@pytest.mark.parametrize(
    "failure",
    ["allowlist", "account", "contact", "title", "duplicate", "windows", "minimized", "permission"],
)
def test_identity_failures_never_write(adapter, bridge, failure):
    if failure == "allowlist":
        adapter.settings.wechat_allowlist = []
    elif failure == "account":
        adapter.profile = adapter.profile.model_copy(update={"account_confirmed": False})
    elif failure == "contact":
        adapter.profile = adapter.profile.model_copy(update={"contacts": ()})
    elif failure == "title":
        bridge.nodes["title"]["AXValue"] = "Other contact"
    elif failure == "duplicate":
        bridge.nodes["duplicate"] = dict(bridge.nodes["session"])
    elif failure == "windows":
        bridge.nodes["root"]["AXWindows"] = []
    elif failure == "minimized":
        bridge.nodes["window"]["AXMinimized"] = True
    elif failure == "permission":
        bridge.available = False
    with pytest.raises(AdapterError):
        adapter.resolve_conversation("a")
    assert bridge.keys == bridge.writes == 0


def test_read_keeps_repeated_bubbles(adapter, bridge):
    adapter.resolve_conversation("a")
    messages, cursor = adapter.poll_events()
    assert len(messages) == 2 and messages[0].text == messages[1].text
    assert messages[0].occurrence_ref != messages[1].occurrence_ref
    assert messages[0].direction == "unknown"
    assert cursor and bridge.keys == bridge.writes == 0


def test_permission_missing_doctor_readonly(adapter, bridge):
    bridge.available = False
    health = adapter.health()
    assert not health.healthy
    assert bridge.keys == bridge.writes == 0


def test_dry_run_never_writes(adapter, bridge):
    candidate = intent(adapter).model_copy(update={"mode": "dry-run"})
    assert adapter.send_text(candidate).outcome == "not_sent"
    assert bridge.keys == bridge.writes == 0


@pytest.mark.parametrize("guard", ["draft", "focus", "mismatch", "allowlist"])
def test_before_send_guards(adapter, bridge, guard):
    candidate = intent(adapter)
    if guard == "draft":
        bridge.nodes["input"]["AXValue"] = "existing draft"
    elif guard == "focus":
        bridge.nodes["input"]["AXFocused"] = False
    elif guard == "mismatch":
        bridge.nodes["title"]["AXValue"] = "Other"
    else:
        adapter.settings.wechat_allowlist = []
    assert adapter.send_text(candidate).outcome == "not_sent"
    assert bridge.keys == bridge.writes == 0


@pytest.mark.parametrize("change", ["title", "focus", "text"])
def test_race_after_filling_input_stops(adapter, bridge, change):
    candidate = intent(adapter)

    def changed(b):
        if change == "title":
            b.nodes["title"]["AXValue"] = "Other"
        elif change == "focus":
            b.nodes["input"]["AXFocused"] = False
        else:
            b.nodes["input"]["AXValue"] = "altered"

    bridge.after_write = changed
    result = adapter.send_text(candidate)
    assert result.outcome == "not_sent" and bridge.keys == 0


def test_return_does_not_claim_delivery(adapter, bridge):
    result = adapter.send_text(intent(adapter))
    assert result.outcome == "unknown" and bridge.keys == 1
    assert "not_delivery_confirmation" in result.basis


def test_key_failure_unknown_never_retried(adapter, bridge):
    bridge.key_error = True
    result = adapter.send_text(intent(adapter))
    assert result.outcome == "unknown" and bridge.keys == 1
    assert "private" not in result.model_dump_json()


def test_unreadable_draft_is_not_empty(adapter, bridge):
    candidate = intent(adapter)
    bridge.nodes["input"].pop("AXValue")
    assert adapter.send_text(candidate).outcome == "not_sent"
    assert bridge.keys == bridge.writes == 0


def test_native_doctor_failure_sanitized(adapter, bridge):
    def fail():
        raise RuntimeError("private desktop data")

    bridge.status = fail
    result = adapter.health()
    assert not result.healthy and result.reason == "native_diagnostic_failed"
    assert "private desktop data" not in result.model_dump_json()


def test_native_status_uses_quartz_console_key():
    from types import SimpleNamespace

    from wechat_reply_agent.adapters.wechat.mac_ax import NativeAX

    bridge = NativeAX.__new__(NativeAX)
    bridge.ax = SimpleNamespace(AXIsProcessTrusted=lambda: True)
    bridge.quartz = SimpleNamespace(
        kCGSessionOnConsoleKey="kCGSSessionOnConsoleKey",
        CGPreflightScreenCaptureAccess=lambda: True,
        CGSessionCopyCurrentDictionary=lambda: {"kCGSSessionOnConsoleKey": True},
    )
    bridge.appkit = SimpleNamespace(
        NSRunningApplication=SimpleNamespace(
            runningApplicationsWithBundleIdentifier_=lambda _: [object()],
        )
    )
    assert bridge.status() == {
        "accessibility": True,
        "screen_recording": True,
        "wechat_running": True,
        "session_unlocked": True,
    }
