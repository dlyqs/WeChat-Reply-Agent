import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.agent.graph import create_graph
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import ConversationRef, Direction, InboundEvent, SendResult
from wechat_reply_agent.llm.client import CompatibleModel, ModelError
from wechat_reply_agent.runtime.prototype import Prototype
from wechat_reply_agent.storage.prototype import Ledger


def event(id="1", text="hello", direction=Direction.INCOMING, conversation="friend", created=100):
    return InboundEvent(
        event_id=id,
        source_message_id=id,
        occurrence_ref=id,
        account_ref="account",
        account_generation="g1",
        native_session=conversation,
        conversation_id=conversation,
        shard="db0",
        local_id=int(id),
        sort_seq=int(id),
        source_created_at=created,
        sender_username=conversation,
        direction=direction,
        text=text,
        confidence=1,
        observed_at=datetime(2020, 1, 1, tzinfo=UTC),
    )


class FakeModel:
    def __init__(self, text="reply", timeout=False):
        self.calls = []
        self.text = text
        self.timeout = timeout

    async def complete(self, messages):
        self.calls.append(messages)
        if self.timeout:
            await asyncio.sleep(10)
        return self.text


class Adapter:
    def __init__(self):
        self.profile = SimpleNamespace(
            account_generation="g1",
            account_ref="account",
            contacts=[SimpleNamespace(alias="test", username="friend")],
        )
        self.events = []
        self.sent = []
        self.outcome = "verified_sent"

    def runtime_binding(self):
        from wechat_reply_agent.adapters.wechat.binding import BoundContact, RuntimeBinding

        return RuntimeBinding("account", "g1", "offline", (BoundContact("test", "friend"),), {})

    def validate_text(self, text):
        pass

    def runtime_info(self):
        return {"platform": "offline", "foundation": "fake", "max_text_characters": 1000}

    def connect(self):
        return {}

    def poll_events(self, cursor=None):
        return self.events.copy(), str(len(self.events))

    def resolve_conversation(self, alias):
        return ConversationRef(
            account_ref="account",
            conversation_id="friend",
            contact_alias="test",
            profile="fake",
            identity_basis="offline",
            confidence=1,
        )

    def send_text(self, intent):
        self.sent.append(intent)
        if intent.mode == "dry-run":
            return SendResult(outcome="not_sent", basis="dry_run")
        return SendResult(outcome=self.outcome, basis="offline")


@pytest.fixture
def setup(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        wechat_account_ref="account",
        wechat_allowlist=["test"],
        send_mode="live",
        coalesce_window_ms=0,
        llm_timeout_seconds=0.02,
    )
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    adapter = Adapter()
    model = FakeModel()
    runtime = Prototype(settings, adapter, model, ledger)
    yield runtime, adapter, model, ledger
    ledger.close()


def test_offline_complete_chain_dedup_and_context(setup):
    r, a, m, db = setup
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    asyncio.run(r.tick())
    assert len(a.sent) == len(m.calls) == 1
    assert db.summary(r.scope)["outbox"] == {"verified_sent": 1}
    assert db.history(r.scope, "friend") == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "reply"},
    ]
    assert db.cursor(r.scope) == "1"


def test_startup_baseline_never_replies_to_old_history(setup):
    r, a, m, db = setup
    a.events = [event()]
    r.start()
    asyncio.run(r.tick())
    assert not a.sent and not m.calls
    assert db.summary(r.scope)["inbox"] == {"baseline": 1}


@pytest.mark.parametrize(
    "direction,conversation",
    [("outgoing", "friend"), ("system", "friend"), ("unknown", "friend"), ("incoming", "other")],
)
def test_filtered_inputs_do_not_call_model(setup, direction, conversation):
    r, a, m, db = setup
    r.start()
    a.events = [event(direction=direction, conversation=conversation)]
    asyncio.run(r.tick())
    assert not m.calls and not a.sent
    assert db.summary(r.scope)["inbox"] == {"filtered": 1}


def test_media_retries_after_late_download_without_model_or_cursor_rewind(setup):
    import time

    from wechat_reply_agent.adapters.wechat.local_media import attachment_directory, result
    from wechat_reply_agent.domain.messages import LocalAttachment

    r, a, m, db = setup
    media = event().model_copy(
        update={
            "text": None,
            "type": "voice",
            "attachment": LocalAttachment(kind="voice"),
        }
    )
    available = False

    def acquire(e):
        if not available:
            return result(e, reason="not_downloaded")
        directory = attachment_directory(r.settings.data_dir, e.event_id)
        directory.mkdir(parents=True)
        path = directory / "voice.silk"
        path.write_bytes(b"#!SILK_V3synthetic")
        return result(e, path)

    a.acquire_attachment = acquire
    r.start()
    a.events = [media]
    asyncio.run(r.tick())
    row = db.db.execute("SELECT payload,status FROM inbox").fetchone()
    assert json.loads(row[0])["attachment"]["status"] == "missing"
    assert row[1] == "filtered" and not m.calls and not a.sent
    cursor = db.cursor(r.scope)
    available = True
    db.record_attachment(
        media.event_id, media.attachment.model_copy(update={"checked_at": time.time() - 31}), None
    )
    r.refresh_attachments()
    row = db.db.execute("SELECT payload,status FROM inbox").fetchone()
    assert json.loads(row[0])["attachment"]["status"] == "available"
    assert row[1] == "filtered" and db.cursor(r.scope) == cursor
    assert not m.calls and not a.sent and not db.history(r.scope, "friend")
    # Text in the same conversation is still processed normally.
    a.events = [event(id="2")]
    asyncio.run(r.tick())
    assert len(m.calls) == len(a.sent) == 1


def test_model_timeout_does_not_create_outbox(setup):
    r, a, m, db = setup
    m.timeout = True
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    assert r.reason == "model_timeout" and not a.sent
    assert db.summary(r.scope)["outbox"] == {}
    assert len(m.calls) == 1


def test_unknown_send_stops_and_survives_restart(setup):
    r, a, m, db = setup
    a.outcome = "unknown"
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    asyncio.run(r.tick())
    assert not r.running and len(a.sent) == 1
    with pytest.raises(AdapterError, match="unresolved_outbox_stop_required"):
        db.begin_run()
    db.resolve(a.sent[0].outbox_id, "discarded")
    db.begin_run()
    assert len(a.sent) == 1


def test_transaction_rolls_back_inbox_and_cursor_on_queue_full(setup):
    r, a, m, db = setup
    db.ingest(r.scope, [], "before", r.eligible, 1)
    with pytest.raises(AdapterError, match="queue_full"):
        db.ingest(r.scope, [event("1"), event("2")], "after", r.eligible, 1)
    assert db.cursor(r.scope) == "before"
    assert db.summary(r.scope)["inbox"] == {}


def test_coalescing_and_new_equal_texts_keep_distinct_inputs(setup):
    r, a, m, db = setup
    r.settings.coalesce_window_ms = 1500
    r.start()
    a.events = [event("1"), event("2", created=101), event("3", created=110)]
    asyncio.run(r.tick())
    assert len(a.sent[0].input_event_refs) == 2
    db.db.execute("UPDATE outbox SET attempted_at=0")
    db.db.commit()
    asyncio.run(r.tick())
    assert len(a.sent) == 2 and a.sent[1].input_event_refs == ("3",)


def test_rate_limit_is_persistent_and_no_model_call_during_cooldown(setup):
    r, a, m, db = setup
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    a.events.append(event("2", created=200))
    asyncio.run(r.tick())
    assert len(a.sent) == len(m.calls) == 1
    assert not db.can_send(0, 30, 2)


def test_stop_discards_late_model_result(setup):
    r, a, m, db = setup

    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()

        async def complete(messages):
            entered.set()
            await release.wait()
            return "late"

        m.complete = complete
        r.start()
        a.events = [event()]
        task = asyncio.create_task(r.tick())
        await entered.wait()
        r.stop()
        release.set()
        await task

    asyncio.run(scenario())
    assert not a.sent and db.summary(r.scope)["outbox"] == {}


def test_sending_crash_recovers_as_unknown(setup):
    r, a, m, db = setup
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    db.db.execute("UPDATE outbox SET state='sending'")
    db.db.commit()
    with pytest.raises(AdapterError, match="unresolved_outbox"):
        db.begin_run()
    assert db.summary(r.scope)["outbox"] == {"unknown": 1}


def test_restart_rebaseline_drops_pending_work(setup):
    r, a, m, db = setup
    r.start()
    db.ingest(r.scope, [event()], "1", r.eligible, 10)
    r.start()
    asyncio.run(r.tick())
    assert not a.sent and not m.calls
    assert db.summary(r.scope)["inbox"] == {"paused": 1}


@pytest.mark.parametrize("text", ["", "x" * 501, "bad\x00text"])
def test_invalid_output_never_becomes_outbox(setup, text):
    r, a, m, db = setup
    m.text = text
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    assert not a.sent and r.reason == "output_rejected"


def test_context_budget_drops_history_without_losing_latest_input(setup):
    r, a, m, db = setup
    r.settings.llm_max_input_tokens = 512
    r.settings.agent_persona = "short"
    graph = create_graph(r.settings, m)
    result = asyncio.run(
        graph.ainvoke(
            {
                "events": [event()],
                "history": [
                    {"role": "user", "content": "x" * 1000},
                    {"role": "assistant", "content": "old"},
                ],
            }
        )
    )
    assert result["result"].status == "ready"
    assert len(m.calls[0]) == 2 and m.calls[0][-1]["content"] == "hello"


def test_input_budget_refuses_without_model_call(setup):
    r, a, m, db = setup
    r.start()
    a.events = [event(text="x" * 10000)]
    asyncio.run(r.tick())
    assert not m.calls and not a.sent and r.reason == "input_budget_exceeded"


@pytest.mark.parametrize("http_status", [401, 402, 429, 500])
def test_http_error_is_redacted_and_not_retried(setup, http_status):
    r, a, m, db = setup
    r.settings.llm_api_key = "FAKE_KEY"
    # validate_assignment is not enabled; use model_copy to preserve SecretStr type.
    from pydantic import SecretStr

    r.settings.llm_api_key = SecretStr("FAKE_KEY")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(http_status, json={"error": "PRIVATE_KEY_AND_TEXT"})

    with pytest.raises(ModelError, match=f"^model_http_{http_status}$"):
        asyncio.run(CompatibleModel(r.settings, httpx.MockTransport(handler)).complete([]))
    assert len(calls) == 1


def test_http_success_uses_bounded_non_thinking_request(setup):
    r, a, m, db = setup
    import json

    from pydantic import SecretStr

    r.settings.llm_api_key = SecretStr("FAKE_KEY")

    def handler(request):
        body = json.loads(request.content)
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 128 and body["stream"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "ok", "reasoning_content": "PRIVATE_THOUGHT"},
                    }
                ]
            },
        )

    assert (
        asyncio.run(CompatibleModel(r.settings, httpx.MockTransport(handler)).complete([])) == "ok"
    )


@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "length", "message": {"content": "partial"}},
        {
            "finish_reason": "stop",
            "message": {"content": "reply", "tool_calls": [{"name": "exec"}]},
        },
        {"finish_reason": "stop", "message": {"content": None}},
    ],
)
def test_incomplete_or_tool_response_is_never_sent(setup, choice):
    r, a, m, db = setup
    from pydantic import SecretStr

    r.settings.llm_api_key = SecretStr("FAKE_KEY")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [choice]}))
    with pytest.raises(ModelError):
        asyncio.run(CompatibleModel(r.settings, transport).complete([]))
    assert not a.sent


def test_context_is_scoped_by_account_generation_and_mode(setup):
    r, a, m, db = setup
    r.start()
    a.events = [event()]
    asyncio.run(r.tick())
    assert db.history(r.scope, "other") == []
    assert db.history("g2:account:live", "friend") == []
    assert db.history("g1:account:dry-run", "friend") == []
