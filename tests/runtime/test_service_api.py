"""Offline lifecycle and API tests. These never initialize the native bridge."""

import asyncio
import json
import os
import threading
import time
from collections import deque
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.api.app import create_app
from wechat_reply_agent.cli import probe_lock
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import (
    AdapterCapabilities,
    ConversationRef,
    Health,
    InboundEvent,
    SendResult,
)
from wechat_reply_agent.runtime.service import RuntimeService
from wechat_reply_agent.settings_store import SettingsStore
from wechat_reply_agent.storage.database import Ledger
from wechat_reply_agent.storage.migrations import bind_identity
from wechat_reply_agent.storage.retention import prune_replica_cache

ORIGIN = "http://127.0.0.1:8765"
HEADERS = {"Origin": ORIGIN, "X-WeChat-Agent": "1"}


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while not predicate():
        assert time.monotonic() < deadline, "offline worker did not reach expected state"
        time.sleep(0.01)


def inbound(index=1):
    return InboundEvent(
        event_id=str(index),
        source_message_id=str(index),
        occurrence_ref=str(index),
        account_ref="offline",
        account_generation="g1",
        native_session="friend",
        conversation_id="friend",
        shard="db0",
        local_id=index,
        sort_seq=index,
        sender_username="friend",
        direction="incoming",
        text="synthetic input",
        confidence=1,
    )


class Adapter:
    def __init__(self, root):
        self.profile = SimpleNamespace(
            account_ref="offline",
            account_generation="g1",
            account="offline",
            self_username="self",
            db_root=root,
            contacts=[SimpleNamespace(alias="test", username="friend")],
        )
        self.snapshots = deque([[], [inbound()]])
        self.sent = []
        self.threads = []
        self.outcome = "verified_sent"

    def record(self):
        self.threads.append(threading.get_ident())

    def connect(self):
        self.record()

    def poll_events(self, cursor=None):
        self.record()
        return (self.snapshots.popleft() if self.snapshots else []), "cursor"

    def resolve_conversation(self, alias):
        return ConversationRef(
            account_ref="offline",
            conversation_id="friend",
            contact_alias="test",
            profile="offline",
            identity_basis="offline",
            confidence=1,
        )

    def send_text(self, intent):
        self.record()
        self.sent.append(intent)
        return SendResult(outcome=self.outcome, basis="offline")

    def health(self):
        self.record()
        return Health(
            healthy=True,
            reason="offline_health",
            environment={"secret": "PRIVATE"},
            capabilities=AdapterCapabilities(profile="offline"),
        )


class Model:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()

    async def complete(self, messages):
        self.entered.set()
        while not self.release.is_set():
            await asyncio.sleep(0.01)
        return "synthetic reply"


@pytest.fixture
def system(tmp_path, monkeypatch):
    # Local .env and developer environment must never influence offline tests.
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        wechat_account_ref="offline",
        wechat_allowlist=["test"],
        llm_api_key="SYNTHETIC_SECRET",
        coalesce_window_ms=0,
        send_mode="live",
    )
    store = SettingsStore(tmp_path / ".env", settings)
    adapter, model = Adapter(tmp_path), Model()
    for phase in (1, 2):
        report = tmp_path / f"acceptance/phase-{phase}/report.json"
        report.parent.mkdir(parents=True)
        report.write_text(
            json.dumps(
                {
                    f"g{phase}": "passed",
                    "foundation": "replica",
                    "plan_version": "v4",
                    "mode": "offline_test",
                }
            )
        )
    service = RuntimeService(store, lambda *args, **kwargs: adapter, lambda settings: model)
    yield store, service, adapter, model
    model.release.set()
    service.close()


def test_unique_worker_real_backend_records_and_stop(system):
    store, service, adapter, model = system
    assert service.snapshot()["state"] == "stopped" and not adapter.threads
    service.start()
    wait_for(lambda: len(adapter.sent) == 1)
    service.halt()
    assert len(set(adapter.threads)) == 1
    assert adapter.threads[0] != threading.get_ident()
    assert service.future.done()
    assert service.repo.conversations(10, 0)[0]["message_count"] == 1
    assert service.repo.runs(10, 0)[0]["status"] == "ready"
    assert service.repo.outbox(10, 0)[0]["reply_text"] == "synthetic reply"


def test_pause_late_model_resume_baseline_no_old_send(system):
    store, service, adapter, model = system
    model.release.clear()
    service.start()
    assert model.entered.wait(3)
    pause = threading.Thread(target=lambda: service.halt(pause=True))
    pause.start()
    wait_for(lambda: not service.runtime.running)
    model.release.set()
    pause.join(3)
    assert not pause.is_alive() and not adapter.sent
    assert service.repo.runs(10, 0)[0]["reason"] == "run_generation_expired"
    assert service.snapshot()["state"] == "paused"
    generation = service.snapshot()["generation"]
    adapter.snapshots = deque([[inbound()], [inbound()]])
    service.start(resume=True)
    wait_for(lambda: service.snapshot()["state"] == "running")
    service.halt()
    assert service.snapshot()["generation"] > generation
    assert not adapter.sent and service.repo.outbox(10, 0) == []


def test_unknown_blocks_restart_until_manual_resolution(system):
    store, service, adapter, model = system
    adapter.outcome = "unknown"
    service.start()
    wait_for(lambda: service.future.done())
    assert service.snapshot()["state"] == "degraded"
    service.start()
    wait_for(lambda: service.future.done())
    assert service.snapshot()["reason"] == "unresolved_outbox_stop_required"
    assert len(adapter.sent) == 1
    row = service.repo.outbox(10, 0)[0]
    service.repo.resolve(row["id"], "discarded")
    service.start()
    wait_for(lambda: service.snapshot()["state"] == "running")
    service.halt()
    assert len(adapter.sent) == 1


def test_identity_change_rejected_before_connect(system):
    store, service, adapter, model = system
    service.start()
    wait_for(lambda: adapter.sent)
    service.halt()
    count = len(adapter.threads)
    adapter.profile.account = "different"
    service.start()
    wait_for(lambda: service.future.done())
    assert service.snapshot()["reason"] == "account_or_database_binding_changed"
    assert len(adapter.threads) == count


def test_queue_overflow_degrades_atomically(system):
    store, service, adapter, model = system
    store.settings = store.settings.model_copy(update={"queue_max_size": 1})
    adapter.snapshots = deque([[], [inbound(1), inbound(2)]])
    service.start()
    wait_for(lambda: service.future.done())
    assert service.snapshot()["reason"] == "queue_full_degraded"
    assert not adapter.sent
    assert service.repo.messages("friend", "g1:offline:live", 10, 0) == []


def test_single_instance_cross_platform(tmp_path):
    with probe_lock(tmp_path), pytest.raises(AdapterError, match="another_probe_running"):
        with probe_lock(tmp_path):
            pass
    with probe_lock(tmp_path):
        pass


def test_private_cache_retention_preserves_recent_files_and_ledger(tmp_path):
    cache = tmp_path / "replica" / "generation"
    cache.mkdir(parents=True)
    expired = cache / "old-snapshot.db"
    expired.write_bytes(b"synthetic")
    os.utime(expired, (0, 0))
    recent = cache / "current-key.json"
    recent.write_text("synthetic")
    ledger = tmp_path / "prototype.sqlite3"
    ledger.write_bytes(b"synthetic")
    assert prune_replica_cache(tmp_path, 30) == 1
    assert recent.exists() and ledger.exists() and not expired.exists()


def test_settings_precedence_atomic_save_and_secret_semantics(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("LLM_API_KEY='SYNTHETIC_OLD'\nLLM_MODEL='dotenv-model'\n")
    monkeypatch.setenv("LLM_MODEL", "environment-model")
    store = SettingsStore(path)
    assert store.public()["sources"]["llm_model"] == "environment"
    assert store.settings.llm_model == "environment-model"
    store.patch({"llm_api_key": "", "agent_persona": "quote ' and \\ and\nnewline"})
    assert store.settings.llm_api_key.get_secret_value() == "SYNTHETIC_OLD"
    assert store.settings.agent_persona == "quote ' and \\ and\nnewline"
    old = path.read_bytes()
    with pytest.raises(ValidationError):
        store.patch({"poll_interval_seconds": -1})
    assert path.read_bytes() == old

    def failed(*args):
        raise OSError("synthetic failure")

    monkeypatch.setattr(os, "replace", failed)
    with pytest.raises(OSError):
        store.patch({"llm_model": "new"})
    assert path.read_bytes() == old and store.settings.llm_model == "environment-model"
    monkeypatch.undo()
    store.patch({"clear_llm_api_key": True})
    assert not store.settings.llm_api_key.get_secret_value()
    assert "SYNTHETIC_OLD" not in json.dumps(store.public())


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example", "X-WeChat-Agent": "1"},
        {"Origin": ORIGIN},
        {"Origin": "null", "X-WeChat-Agent": "1"},
    ],
)
def test_api_rejects_foreign_or_missing_write_sources(system, headers):
    store, service, adapter, model = system
    with TestClient(create_app(store, service), base_url=ORIGIN) as client:
        response = client.post("/api/runtime/start", headers=headers, json={})
        assert response.status_code == 403
        assert set(response.json()) == {"code", "message", "trace_id"}
        assert not adapter.threads


def test_api_contract_security_errors_settings_diagnostics_and_static(system):
    store, service, adapter, model = system
    with TestClient(create_app(store, service), base_url=ORIGIN) as client:
        assert client.get("/api/health").json()["runtime"]["state"] == "stopped"
        assert client.get("/api/health", headers={"Host": "evil.example:8765"}).status_code == 403
        assert (
            client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 403
        )
        response = client.get("/api/settings")
        assert response.status_code == 200
        assert "SYNTHETIC_SECRET" not in response.text
        assert "llm_api_key" not in response.json()["values"]
        response = client.patch(
            "/api/settings",
            headers=HEADERS,
            json={"llm_api_key": "bad-secret", "poll_interval_seconds": -2},
        )
        assert response.status_code == 422 and "bad-secret" not in response.text
        assert client.get("/api/runs/999").status_code == 404
        assert client.get("/api/runs/not-an-int").status_code == 422
        assert client.get("/api/conversations?limit=101").status_code == 422
        response = client.post("/api/diagnostics", headers=HEADERS, json={})
        assert response.status_code == 200 and "PRIVATE" not in response.text
        assert not response.json()["connected"]
        assert client.post("/api/runtime/start", headers=HEADERS, json={}).status_code == 200
        wait_for(lambda: len(adapter.sent) == 1)
        assert (
            client.patch("/api/settings", headers=HEADERS, json={"llm_model": "x"}).status_code
            == 409
        )
        assert client.post("/api/runtime/stop", headers=HEADERS, json={}).status_code == 200
        c = client.get("/api/conversations").json()["items"][0]
        assert (
            client.get(
                f"/api/conversations/{c['id']}/messages", params={"scope": c["scope"]}
            ).json()["items"][0]["text"]
            == "synthetic input"
        )
        assert client.get("/api/runs").json()["items"][0]["reply_text"] == "synthetic reply"
        response = client.get("/")
        assert response.status_code == 200 and "root" in response.text
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert client.get("/not-a-route").json()["code"] == "route_not_found"
        response = client.patch(
            "/api/settings", headers=HEADERS, json={"agent_persona": "x" * 70000}
        )
        assert response.status_code == 413


def test_api_manual_unknown_resolution_updates_actual_ledger(system):
    store, service, adapter, model = system
    adapter.outcome = "unknown"
    with TestClient(create_app(store, service), base_url=ORIGIN) as client:
        client.post("/api/runtime/start", headers=HEADERS, json={})
        wait_for(lambda: service.future.done())
        row = client.get("/api/outbox").json()["items"][0]
        path = f"/api/outbox/{row['id']}/resolve"
        assert client.post(path, headers=HEADERS, json={"resolution": "retry"}).status_code == 409
        assert client.post(path, headers=HEADERS, json={"resolution": "sent"}).status_code == 200
        assert client.get("/api/outbox").json()["items"][0]["resolution"] == "sent"
        assert len(adapter.sent) == 1


def test_paused_intent_requires_manual_resolution_and_replacement_detected(system):
    store, service, adapter, model = system
    service.start()
    wait_for(lambda: adapter.sent)
    service.halt()
    ledger = Ledger(service.path)
    with ledger.db:
        ledger.db.execute("UPDATE outbox SET state='pending'")
    with pytest.raises(AdapterError, match="unresolved_outbox"):
        ledger.begin_run()
    row = ledger.db.execute("SELECT id,state FROM outbox").fetchone()
    assert row[1] == "paused"
    ledger.resolve(row[0], "discarded")
    ledger.begin_run()
    ledger.close()
    original = service.file_identity
    service.file_identity = (original[0], -1)
    with pytest.raises(AdapterError, match="application_database_replaced"):
        service.start()
    service.file_identity = original
    backup = service.path.with_name("ledger.saved")
    service.path.rename(backup)
    try:
        assert not service._same_database()
        assert service.halt()["state"] == "stopped"
        assert not service.path.exists()
    finally:
        backup.rename(service.path)


def test_migration_keeps_v1_ids_cursor_context_and_outbox(system):
    store, service, adapter, model = system
    service.start()
    wait_for(lambda: adapter.sent)
    service.halt()
    ledger = Ledger(service.path)
    before = ledger.db.execute("SELECT id,input_key,intent FROM outbox").fetchall()
    # Remove only additive v2 schema to emulate the exact v1 layout.
    ledger.db.executescript("""
        DROP TRIGGER inbox_status_update;
        DROP TABLE messages; DROP TABLE contacts; DROP TABLE conversations; DROP TABLE metadata;
        ALTER TABLE runtime_state DROP COLUMN state;
        ALTER TABLE runtime_state DROP COLUMN reason;
        PRAGMA user_version=1;
    """)
    ledger.close()
    migrated = Ledger(service.path)
    assert migrated.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert [
        tuple(row) for row in migrated.db.execute("SELECT id,input_key,intent FROM outbox")
    ] == [tuple(row) for row in before]
    assert migrated.cursor("g1:offline:live") == "cursor"
    assert migrated.history("g1:offline:live", "friend")[1]["content"] == "synthetic reply"
    assert migrated.db.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
    with pytest.raises(AdapterError, match="binding_changed"):
        bind_identity(migrated.db, "new", "other-account", "g2")
    migrated.close()
