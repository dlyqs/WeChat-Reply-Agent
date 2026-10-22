"""Synthetic native ports exercise the real Mac adapter, runtime, ledger and API."""

import asyncio
import hashlib
import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_acceptance import context
from wechat_reply_agent.adapters.wechat.mac_db import MacAdapter
from wechat_reply_agent.adapters.wechat.mac_profile import MacProfile
from wechat_reply_agent.api.app import create_app
from wechat_reply_agent.cli import write_private
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import SendIntent
from wechat_reply_agent.runtime.service import RuntimeService
from wechat_reply_agent.settings_store import SettingsStore


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.01)


class Native:
    def __init__(self):
        self.rows, self.threads = [], []
        self.crash = False
        self.attempts = 0

    def note(self):
        self.threads.append(threading.get_ident())

    def connect(self):
        self.note()
        return {"account": "verified", "keys": "verified", "gui": "available"}

    def assert_session(self):
        self.note()

    def snapshot(self, username):
        self.note()
        return {"salts": {"message_0.db": "same"}, "cursor": {"message_0.db": len(self.rows)}}

    def read(self, username, after=None, limit=200):
        self.note()
        if after is None:
            return self.rows[-limit:]
        return [r for r in self.rows if r["local_id"] > (after or {}).get("message_0.db", 0)][
            :limit
        ]

    def append(self, sender, text):
        self.rows.append(
            {
                "database": "message_0.db",
                "local_id": len(self.rows) + 1,
                "create_time": 100,
                "local_type": 1,
                "sender_id": sender,
                "text": text,
            }
        )

    def send_once(self, intent):
        self.note()
        self.attempts += 1
        if self.crash:
            raise RuntimeError("private native diagnostics")
        self.append("self", intent.reply_text)
        return {"attempted": True}

    def close(self):
        self.note()


class Model:
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()

    async def complete(self, messages):
        self.entered.set()
        while not self.release.is_set():
            await asyncio.sleep(0.01)
        return "慢慢来，我在听。\nTake your time  🙂"


@pytest.fixture
def mac(tmp_path, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_acceptance, mac_db

    monkeypatch.setattr(mac_acceptance.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac_acceptance, "client_version", lambda p: ("4.synthetic", "1"))
    monkeypatch.setattr(
        mac_db,
        "environment",
        lambda s: {
            "platform": "Darwin",
            "architecture": "arm64",
            "sqlcipher_available": True,
            "bridge_built": True,
            "screen_locked": False,
            "accessibility": True,
            "screen_recording": False,
            "wechat_running": True,
            "private": "HIDDEN",
        },
    )
    root = tmp_path / "db_storage"
    root.mkdir()
    (root / "message_0.db").write_bytes(b"stable salt!!!!!")
    profile = MacProfile(
        account_ref="offline",
        account_generation="g1",
        self_username="self",
        db_root=root,
        key_file=tmp_path / "keys.json",
        wechat_version="4.synthetic",
        wechat_build="1",
        account_confirmed=True,
        composer_top=0.775,
        window_width=598,
        window_height=640,
        window_mode="independent",
        send_preflight="ax-window-db",
        contacts=(
            {
                "alias": "friend",
                "username": "friend",
                "title": "Unique friend",
                "wechat_id": "friend",
                "single_chat_confirmed": True,
            },
        ),
    )
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        wechat_adapter="mac_db",
        wechat_account_ref="offline",
        wechat_allowlist=["friend"],
        send_mode="live",
        llm_api_key="SYNTHETIC",
        coalesce_window_ms=0,
        mac_verify_timeout_seconds=1,
    )
    expected = context(profile)
    directory = tmp_path / "acceptance/mac/phase-5"
    write_private(
        directory / "degraded-flow.json",
        expected
        | {
            "status": "passed",
            "acceptance_mode": "user_authorized_degraded_flow",
            "user_confirmed_success": True,
            "recipient_confirmed": True,
            "real_model_rounds": 2,
            "evidence_mode": "synthetic",
        },
    )
    write_private(
        directory / "degraded-fixed-send.json",
        expected
        | {"outcome": "verified_sent", "basis": "local_db_confirmed", "outbox_id": "fixed"},
    )
    write_private(
        tmp_path / "macos/operations" / (hashlib.sha256(b"fixed").hexdigest() + ".json"),
        {"result": {"outcome": "verified_sent"}},
    )
    native, model = Native(), Model()
    adapter = MacAdapter(settings, profile, native)
    store = SettingsStore(tmp_path / ".env", settings)
    service = RuntimeService(store, lambda *a, **k: adapter, lambda s: model)

    class FastEvent(threading.Event):
        def wait(self, timeout=None):
            return super().wait(min(timeout or 0.01, 0.01))

    service.cancel = FastEvent()
    yield SimpleNamespace(
        store=store,
        service=service,
        adapter=adapter,
        native=native,
        model=model,
        report=directory / "degraded-flow.json",
    )
    model.release.set()
    service.close()


def test_mac_formal_worker_preserves_multiline_and_uses_one_native_thread(mac):
    mac.service.start()
    wait_for(lambda: mac.service.connected)
    mac.native.append("friend", "今天工作有点累，想找个人聊聊。")
    wait_for(lambda: mac.native.attempts == 1)
    mac.service.halt()
    outbox = mac.service.repo.outbox(10, 0)
    assert outbox[0]["state"] == "verified_sent"
    assert outbox[0]["reply_text"] == "慢慢来，我在听。\nTake your time  🙂"
    assert len(set(mac.native.threads)) == 1
    assert mac.native.threads[0] != threading.get_ident()
    assert mac.service.snapshot()["capabilities"]["ui_checks_degraded"]


def test_mac_startup_history_is_visible_without_model_or_old_replies(mac):
    from wechat_reply_agent.adapters.wechat.local_media import result

    mac.native.append("friend", "before startup")
    mac.native.rows.append(
        {
            "database": "message_0.db",
            "local_id": 2,
            "create_time": 101,
            "local_type": 34,
            "sender_id": "friend",
            "text": None,
        }
    )
    # An unavailable old voice is still displayed, and acquisition is independent of the LLM.
    mac.native.acquire_attachment = lambda event: result(event, reason="not_downloaded")
    mac.service.start()
    wait_for(lambda: mac.service.connected)
    rows = mac.service.repo.messages("friend", mac.service.runtime.scope, 10, 0)
    assert len(rows) == 2 and {row["status"] for row in rows} == {"baseline"}
    assert rows[0]["type"] == "voice" and rows[0]["attachment"]["status"] == "missing"
    assert rows[1]["text"] == "before startup" and rows[1]["source_created_at"] == 100
    assert not mac.model.entered.is_set() and mac.native.attempts == 0
    assert not mac.service.repo.runs(10, 0)
    mac.native.append("friend", "new after startup")
    wait_for(lambda: mac.native.attempts == 1)
    mac.service.halt()
    assert len(mac.service.repo.runs(10, 0)) == 1
    # Reconnecting does not resurrect baseline messages as pending replies.
    mac.service.start()
    wait_for(lambda: mac.service.connected)
    mac.service.halt()
    assert mac.native.attempts == 1


def test_mac_pause_cancels_late_model_and_resume_rebaselines(mac):
    mac.model.release.clear()
    mac.service.start()
    wait_for(lambda: mac.service.connected)
    mac.native.append("friend", "晚上想去散散步。")
    assert mac.model.entered.wait(3)
    thread = threading.Thread(target=lambda: mac.service.halt(pause=True))
    thread.start()
    wait_for(lambda: not mac.service.runtime.running)
    mac.model.release.set()
    thread.join(3)
    assert mac.native.attempts == 0 and mac.service.snapshot()["state"] == "paused"
    mac.service.start(resume=True)
    wait_for(lambda: mac.service.connected)
    mac.service.halt()
    assert mac.native.attempts == 0


def test_mac_api_unknown_resolution_updates_native_and_application_journals(mac):
    mac.native.crash = True
    origin = "http://127.0.0.1:8765"
    headers = {"Origin": origin, "X-WeChat-Agent": "1"}
    with TestClient(create_app(mac.store, mac.service), base_url=origin) as client:
        diagnostic = client.post("/api/diagnostics", json={}, headers=headers)
        assert diagnostic.json()["platform"] == "macOS" and "HIDDEN" not in diagnostic.text
        assert client.get("/api/health").json()["foundation"] == "mac_db"
        client.post("/api/runtime/start", headers=headers, json={})
        wait_for(lambda: mac.service.connected)
        mac.native.append("friend", "周末想一起去公园吗？")
        wait_for(lambda: mac.service.future.done())
        row = mac.service.repo.outbox(10, 0)[0]
        assert row["state"] == "unknown"
        operation = (
            mac.store.settings.data_dir
            / "macos/operations"
            / (hashlib.sha256(row["id"].encode()).hexdigest() + ".json")
        )
        assert (
            client.post(
                f"/api/outbox/{row['id']}/resolve",
                headers=headers,
                json={"resolution": "discarded"},
            ).status_code
            == 200
        )
        assert json.loads(operation.read_text())["resolution"] == "discarded"
        assert mac.native.attempts == 1


@pytest.mark.parametrize(
    "wrong",
    [
        {"platform": "Windows"},
        {"foundation": "replica"},
        {"binding_fingerprint": "other"},
        {"wechat_version": "other"},
        {"user_confirmed_success": False},
    ],
)
def test_mac_service_rejects_mismatched_acceptance_before_native_connect(mac, wrong):
    write_private(mac.report, json.loads(mac.report.read_text()) | wrong)
    mac.service.start()
    wait_for(lambda: mac.service.future.done())
    assert mac.service.reason == "mac_matching_degraded_acceptance_required"
    assert mac.native.attempts == 0 and mac.service.runtime is None


def test_mac_source_salt_change_stops_even_if_file_inode_is_unchanged(mac):
    mac.service.start()
    wait_for(lambda: mac.service.connected)
    path = mac.adapter.profile.db_root / "message_0.db"
    inode = path.stat().st_ino
    path.write_bytes(b"replaced salt!!!")
    assert path.stat().st_ino == inode
    with pytest.raises(AdapterError, match="native_database_replaced"):
        mac.service.check_database()


def test_mac_new_voice_database_preserves_acceptance_and_ledger_anchor(mac):
    mac.service.start()
    wait_for(lambda: mac.service.connected)
    mac.service.halt()
    original_binding = mac.adapter.runtime_binding().fingerprint
    flow = mac.report.read_bytes()
    fixed_path = mac.report.parent / "degraded-fixed-send.json"
    fixed = fixed_path.read_bytes()
    media = mac.adapter.profile.db_root / "message/media_0.db"
    media.parent.mkdir()
    media.write_bytes(b"new voice identity")
    binding = mac.adapter.runtime_binding()
    assert binding.fingerprint == original_binding
    assert media in binding.source_files
    mac.service.start()
    wait_for(lambda: mac.service.connected or mac.service.future.done())
    assert mac.service.connected and mac.service.state == "running"
    mac.service.halt()
    assert mac.report.read_bytes() == flow and fixed_path.read_bytes() == fixed
    assert mac.native.attempts == 0


def test_mac_new_voice_database_does_not_hide_original_source_replacement(mac):
    root = mac.adapter.profile.db_root
    (root / "message").mkdir()
    (root / "message/media_0.db").write_bytes(b"new voice identity")
    (root / "message_0.db").write_bytes(b"replaced identity")
    mac.service.start()
    wait_for(lambda: mac.service.future.done())
    assert mac.service.reason == "mac_matching_degraded_acceptance_required"
    assert mac.service.runtime is None and mac.native.attempts == 0


def test_mac_only_settings_are_applicable_and_visual_flags_are_inactive(mac):
    public = mac.store.public()
    assert "wechat_uia_gate_enabled" in public["inactive"]
    assert "mac_bridge_path" not in public["inactive"]
    with pytest.raises(AdapterError, match="not_applicable"):
        mac.store.patch({"wechat_uia_gate_enabled": False})


@pytest.mark.parametrize(
    "text",
    [
        "晚饭吃什么？",
        "Take your time  🙂 👨‍👩‍👧‍👦",
        "今天有点累。\n明天再聊吧。",
        "  晚安，好好休息。  ",
        "晚" * 1000,
    ],
)
def test_mac_text_matrix_preserves_full_payload(mac, text):
    mac.adapter.connect()
    intent = SendIntent(
        conversation=mac.adapter.resolve_conversation("friend"), reply_text=text, mode="live"
    )
    assert mac.adapter.send_text(intent).outcome == "verified_sent"
    assert mac.native.rows[-1]["text"] == text


@pytest.mark.parametrize("text", ["晚" * 1001, "晚\r安", "晚\t安", "晚\x00安"])
def test_mac_unsupported_text_is_rejected_before_any_native_action(mac, text):
    with pytest.raises(AdapterError, match="text_unsupported"):
        mac.adapter.validate_text(text)
    assert not mac.native.threads


def test_unresolved_native_only_operation_blocks_formal_start_before_model(mac):
    path = mac.store.settings.data_dir / "macos/operations/interrupted.json"
    write_private(path, {"status": "prepared", "outbox_id": "interrupted"})
    mac.service.start()
    wait_for(lambda: mac.service.future.done())
    assert mac.service.reason == "unresolved_native_operation_stop_required"
    assert not mac.model.entered.is_set() and mac.native.attempts == 0


def test_clock_gap_degrades_before_processing_after_resume(monkeypatch):
    from wechat_reply_agent.runtime import worker

    wall = iter([100, 100, 400])
    mono = iter([100, 100, 101])
    monkeypatch.setattr(
        worker, "time", SimpleNamespace(time=lambda: next(wall), monotonic=lambda: next(mono))
    )

    class Runtime:
        running = True
        sent_count = 0
        reason = "running"
        ticks = 0

        def start(self):
            pass

        def stop(self, reason):
            self.running, self.reason = False, reason

        async def tick(self):
            self.ticks += 1

    runtime = Runtime()
    service = SimpleNamespace(
        guard=threading.RLock(),
        state="starting",
        connected=False,
        repo=SimpleNamespace(runtime_state=lambda *a: 1),
        settings=Settings(_env_file=None),
        check_database=lambda: None,
        cancel=SimpleNamespace(is_set=lambda: False, wait=lambda duration: None),
    )
    asyncio.run(worker.run_worker(service, runtime))
    assert runtime.ticks == 1
    assert service.state == "degraded" and service.reason == "desktop_resume_reconnect_required"
