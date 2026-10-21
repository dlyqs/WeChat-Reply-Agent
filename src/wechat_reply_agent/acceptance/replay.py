"""Exercise the production service with synthetic adapters and a local deterministic model."""

import asyncio
import json
import tempfile
import threading
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from wechat_reply_agent.adapters.wechat.binding import BoundContact, RuntimeBinding
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import ConversationRef, InboundEvent, SendResult
from wechat_reply_agent.knowledge.store import KnowledgeStore
from wechat_reply_agent.llm.client import ModelError
from wechat_reply_agent.memory.store import MemoryStore
from wechat_reply_agent.runtime.service import RuntimeService
from wechat_reply_agent.settings_store import SettingsStore
from wechat_reply_agent.storage.database import Ledger


def inbound(index=1, text="合成问候", direction="incoming"):
    return InboundEvent(
        event_id=f"synthetic-{index}",
        source_message_id=f"synthetic-{index}",
        occurrence_ref=f"synthetic-{index}",
        account_ref="synthetic",
        account_generation="g1",
        native_session="friend",
        conversation_id="friend",
        shard="synthetic-db",
        local_id=index,
        sort_seq=index,
        sender_username="friend" if direction == "incoming" else "self",
        direction=direction,
        text=text,
        confidence=1,
        source_created_at=100,
    )


class ReplayAdapter:
    def __init__(self, platform, snapshots):
        self.platform = platform
        self.snapshots = deque(snapshots)
        self.sent = []
        self.outcome = "verified_sent"

    def runtime_binding(self):
        return RuntimeBinding(
            "synthetic",
            "g1",
            "synthetic",
            (BoundContact("test", "friend"), BoundContact("other", "other-friend")),
            {},
        )

    def runtime_info(self):
        return {
            "platform": self.platform,
            "foundation": "offline_replay",
            "max_text_characters": 1000,
            "evidence": "synthetic_only",
        }

    def require_runtime_acceptance(self, binding):
        pass

    def prune_cache(self):
        pass

    def validate_text(self, text):
        pass

    def connect(self):
        return {}

    def close(self):
        pass

    def resolve_conversation(self, alias):
        return ConversationRef(
            account_ref="synthetic",
            conversation_id="friend",
            contact_alias=alias,
            profile="synthetic",
            identity_basis="offline_replay_only",
            confidence=1,
        )

    def poll_events(self, cursor=None):
        return (self.snapshots.popleft() if self.snapshots else []), "synthetic-cursor"

    def send_text(self, intent):
        self.sent.append(intent)
        return SendResult(outcome=self.outcome, basis="offline_replay_only")

    def public_error(self, exc):
        return "offline_replay_failed"


class ReplayModel:
    def __init__(self):
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.fail = False

    async def complete(self, messages):
        self.calls.append(messages)
        self.entered.set()
        while not self.release.is_set():
            await asyncio.sleep(0.005)
        if self.fail:
            raise ModelError("model_request_failed")
        return "这是一条离线合成回复。"


def wait_for(predicate):
    deadline = time.monotonic() + 5
    while not predicate():
        if time.monotonic() >= deadline:
            raise RuntimeError("replay_deadline_exceeded")
        time.sleep(0.005)


def run_case(root, platform, name):
    event = inbound()
    if name == "dedup_same_text_and_filters":
        events = [
            event,
            event,
            inbound(2),
            inbound(3, direction="outgoing"),
            inbound(4, direction="unknown"),
        ]
    elif name == "knowledge_and_memory":
        events = [inbound(text="记住我的偏好：饮品=乌龙茶")]
    elif name in ("pause_late_model", "model_failure"):
        events = [inbound(text="记住我的偏好：饮品=不应保存")]
    else:
        events = [event]
    adapter, model = ReplayAdapter(platform, [[], events]), ReplayModel()
    overrides = {
        "data_dir": root,
        "wechat_adapter": "mac_db" if platform == "macOS" else "replica",
        "wechat_account_ref": "synthetic",
        "wechat_allowlist": ["test"],
        "send_mode": "live",
        "llm_api_key": "SYNTHETIC_OFFLINE_ONLY",
        "coalesce_window_ms": 0,
    }
    settings = Settings(
        _env_file=None,
        **(
            {
                key: field.get_default(call_default_factory=True)
                for key, field in Settings.model_fields.items()
            }
            | overrides
        ),
    )
    # No dotenv or inherited account settings are loaded, and factories cannot access native code.
    store = SettingsStore(root / ".env", settings)
    service = RuntimeService(store, lambda *a, **kw: adapter, lambda s: model)
    scope = "g1:synthetic:live"
    try:
        if name == "model_failure":
            model.fail = True
        if name == "unknown_restart":
            adapter.outcome = "unknown"
        if name == "knowledge_and_memory":
            KnowledgeStore(service.path).import_text("合成茶店.md", "乌龙茶价格18元。")
        if name == "pause_late_model":
            model.release.clear()
        service.start()
        if name == "pause_late_model":
            wait_for(model.entered.is_set)
            thread = threading.Thread(target=lambda: service.halt(pause=True))
            thread.start()
            wait_for(service.cancel.is_set)
            model.release.set()
            thread.join(timeout=5)
            assert not thread.is_alive()
            assert not adapter.sent and not MemoryStore(service.path).read(scope, "friend")
            assert service.repo.runs(5, 0)[0]["status"] == "cancelled"
            service.start(resume=True)
            wait_for(lambda: service.snapshot()["state"] == "running")
            service.halt()
            assert not adapter.sent
        elif name == "model_failure":
            wait_for(lambda: service.snapshot()["state"] == "degraded")
            assert (
                not adapter.sent and service.repo.runs(5, 0)[0]["reason"] == "model_request_failed"
            )
            assert not MemoryStore(service.path).read(scope, "friend")
        elif name == "unknown_restart":
            wait_for(lambda: service.snapshot()["state"] == "degraded")
            service.halt()
            service.start()
            wait_for(lambda: service.snapshot()["state"] == "degraded")
            assert len(adapter.sent) == 1 and service.reason == "unresolved_outbox_stop_required"
        else:
            wait_for(
                lambda: (
                    bool(service.repo.outbox(5, 0))
                    and service.repo.outbox(5, 0)[0]["state"] == "verified_sent"
                )
            )
            service.halt()
            assert len(adapter.sent) == 1 and len(model.calls) == 1
            if name == "dedup_same_text_and_filters":
                ledger = Ledger(service.path)
                try:
                    assert ledger.summary(scope)["inbox"] == {"processed": 2, "filtered": 2}
                    assert len(adapter.sent[0].input_event_refs) == 2
                finally:
                    ledger.close()
            elif name == "knowledge_and_memory":
                memory = MemoryStore(service.path)
                assert memory.read(scope, "friend")[0]["value"] == "乌龙茶"
                assert not memory.read(scope, "other-friend")
                assert service.repo.runs(1, 0)[0]["sources"]
                service.close()
                service = RuntimeService(store, lambda *a, **kw: adapter, lambda s: model)
                # Advance synthetic send time; the real service's rate limiter stays unchanged.
                ledger = Ledger(service.path)
                with ledger.db:
                    ledger.db.execute("UPDATE outbox SET attempted_at=0")
                ledger.close()
                adapter.snapshots = deque([[], [inbound(2, text="我偏好什么饮品？")]])
                service.start()
                wait_for(lambda: len(adapter.sent) == 2)
                service.halt()
                assert "乌龙茶" in json.dumps(model.calls[-1], ensure_ascii=False)
                memory.change(scope, "friend", "饮品", "白茶")
                assert memory.read(scope, "friend")[0]["value"] == "白茶"
                memory.change(scope, "friend", "饮品", None)
                assert not memory.read(scope, "friend")
                knowledge = KnowledgeStore(service.path)
                knowledge.delete(knowledge.documents()[0]["id"])
                assert not knowledge.search("乌龙茶")
            elif name == "crash_recovery":
                ledger = Ledger(service.path)
                with ledger.db:
                    ledger.db.execute("UPDATE outbox SET state='sending',result=NULL")
                    ledger.db.execute("UPDATE inbox SET status='processing'")
                ledger.close()
    finally:
        model.release.set()
        service.close()
    # Reconstruct the real service to check durable state, without connecting.
    reopened = RuntimeService(store, lambda *a, **kw: adapter, lambda s: model)
    try:
        assert reopened.snapshot()["state"] == "stopped"
        assert len(adapter.sent) <= (2 if name == "knowledge_and_memory" else 1)
        if name == "crash_recovery":
            assert reopened.repo.outbox(1, 0)[0]["state"] == "unknown"
            assert reopened.repo.messages("friend", scope, 1, 0)[0]["status"] == "paused"
    finally:
        reopened.close()


def replay(suite="all"):
    cases = []
    for platform in ("Windows", "macOS"):
        for name in (
            "dedup_same_text_and_filters",
            "model_failure",
            "unknown_restart",
            "pause_late_model",
            "knowledge_and_memory",
            "crash_recovery",
        ):
            with tempfile.TemporaryDirectory(prefix="wechat-offline-replay-") as folder:
                try:
                    run_case(Path(folder), platform, name)
                    status = "passed"
                except Exception:
                    status = "failed"
            cases.append(
                {
                    "case": name,
                    "platform": platform,
                    "status": status,
                    "evidence": "production_service_with_synthetic_adapter_and_model",
                }
            )
    return {
        "phase": 9,
        "plan_version": "v5",
        "suite": suite,
        "created": datetime.now(UTC).isoformat(),
        "mode": "offline",
        "status": "passed" if all(c["status"] == "passed" for c in cases) else "failed",
        "cases": cases,
        "native_wechat": "not_tested",
        "human_acceptance": "not_tested",
    }
