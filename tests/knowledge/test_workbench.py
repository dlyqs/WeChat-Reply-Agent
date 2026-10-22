import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from wechat_reply_agent.acceptance.replay import ReplayAdapter, inbound
from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.agent.graph import AgentResult, input_cost
from wechat_reply_agent.agent.personas import NORTHLINE
from wechat_reply_agent.api.app import create_app
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import ConversationRef, SendIntent, SendResult
from wechat_reply_agent.knowledge.demo import BASE_ID, QUESTIONS, seed_demo
from wechat_reply_agent.knowledge.store import KnowledgeStore
from wechat_reply_agent.memory.store import MemoryStore
from wechat_reply_agent.runtime.service import RuntimeService
from wechat_reply_agent.settings_store import SettingsStore
from wechat_reply_agent.storage.database import Ledger
from wechat_reply_agent.storage.repositories import Repository

SCOPE = "g1:synthetic:live"
HEADERS = {"Origin": "http://127.0.0.1:8765", "X-WeChat-Agent": "1"}


class Model:
    def __init__(self):
        self.messages = []

    async def complete(self, messages):
        self.messages = messages
        return "冬季密封圈编号为 NR-24B，适用于5–15℃，不用于零下萃取。"


@pytest.fixture
def system(tmp_path, monkeypatch):
    for key in Settings.model_fields:
        monkeypatch.delenv(key.upper(), raising=False)
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        wechat_profile=tmp_path / "not-bound.json",
        wechat_account_ref="synthetic",
        wechat_allowlist=["test"],
        llm_api_key="SYNTHETIC_KEY",
        agent_persona=NORTHLINE,
    )
    store = SettingsStore(tmp_path / ".env", settings)
    adapter, model = ReplayAdapter("Windows", [[], []]), Model()
    service = RuntimeService(store, lambda *a, **kw: adapter, lambda s: model)
    with TestClient(create_app(store, service), base_url="http://127.0.0.1:8765") as client:
        yield client, service, model, adapter


def add_turn(path, index, contact="friend", outcome="verified_sent"):
    ledger = Ledger(path)
    event = inbound(index, text=f"PRIVATE_SYNTHETIC_INBOUND_{index}").model_copy(
        update={"conversation_id": contact, "native_session": contact, "sender_username": contact}
    )
    with ledger.db:
        ledger.db.execute("INSERT OR IGNORE INTO contacts VALUES(?,?,?)", (SCOPE, contact, contact))
        ledger.db.execute("INSERT OR IGNORE INTO metadata VALUES('binding','keep-binding')")
    ledger.ingest(SCOPE, [event], "preserved-cursor", lambda e: True, 100)
    intent = SendIntent(
        conversation=ConversationRef(
            account_ref="synthetic",
            conversation_id=contact,
            contact_alias=contact,
            profile="synthetic",
            confidence=1,
            identity_basis="offline",
        ),
        reply_text=f"PRIVATE_SYNTHETIC_REPLY_{index}",
        mode="live",
    )
    result = AgentResult(status="ready", reason="validated", reply_text=intent.reply_text)
    run_id = ledger.finish_model(SCOPE, [event], result, intent, 20, 1)
    ledger.sending(intent.outbox_id, time.time())
    ledger.sent(SCOPE, intent, [event], SendResult(outcome=outcome, basis="synthetic"), run_id, 2)
    ledger.close()
    return event, intent


def test_history_redacts_selected_content_and_preserves_dedup_binding_and_limits(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    event, _ = add_turn(path, 1)
    add_turn(path, 2, "other")
    MemoryStore(path).change(SCOPE, "friend", "偏好", "PRIVATE_PREFERENCE")
    knowledge = KnowledgeStore(path)
    knowledge.import_text("retained.md", "必须保留的产品知识。")
    repo = Repository(path)
    result = repo.clear_history(SCOPE, "friend")
    assert result["cleared"] == {"inbox": 1, "outbox": 1, "run": 1, "memories": 0}
    assert not repo.messages("friend", SCOPE, 10, 0)
    assert [c["id"] for c in repo.conversations(10, 0)] == ["other"]
    assert len(repo.outbox(10, 0)) == len(repo.runs(10, 0)) == 1
    assert MemoryStore(path).read(SCOPE, "friend")[0]["value"] == "PRIVATE_PREFERENCE"
    ledger = Ledger(path)
    assert ledger.cursor(SCOPE) == "preserved-cursor"
    assert (
        ledger.db.execute("SELECT value FROM metadata WHERE key='binding'").fetchone()[0]
        == "keep-binding"
    )
    assert not ledger.can_send(time.time(), 30, 2)
    for table in ("inbox", "messages", "outbox", "agent_runs", "context"):
        text = json.dumps([dict(r) for r in ledger.db.execute("SELECT * FROM " + table)])
        assert "PRIVATE_SYNTHETIC_INBOUND_1" not in text and "PRIVATE_SYNTHETIC_REPLY_1" not in text
    assert ledger.ingest(SCOPE, [event], "next-cursor", lambda e: True, 100) == 0
    assert not repo.messages("friend", SCOPE, 10, 0)
    new_event = inbound(3).model_copy(update={"conversation_id": "friend"})
    assert ledger.ingest(SCOPE, [new_event], "new-cursor", lambda e: True, 100) == 1
    assert len(repo.messages("friend", SCOPE, 10, 0)) == 1
    ledger.close()
    repo.clear_history(forget_memories=True)
    assert (
        repo.dashboard()["messages"] == repo.dashboard()["replies"] == repo.dashboard()["runs"] == 0
    )
    assert not MemoryStore(path).read(SCOPE, "friend")
    assert knowledge.search("产品知识")


@pytest.mark.parametrize("outcome", ["unknown", "paused", "sending", "pending"])
def test_clearing_cannot_remove_unresolved_send_evidence(tmp_path, outcome):
    path = tmp_path / "ledger.sqlite3"
    _, intent = add_turn(path, 1)
    ledger = Ledger(path)
    with ledger.db:
        ledger.db.execute(
            "UPDATE outbox SET state=?,resolution=NULL WHERE id=?", (outcome, intent.outbox_id)
        )
    ledger.close()
    repo = Repository(path)
    with pytest.raises(AdapterError, match="history_unresolved_outbox"):
        repo.clear_history()
    assert repo.outbox(10, 0)[0]["reply_text"] == intent.reply_text
    assert repo.messages("friend", SCOPE, 10, 0)[0]["text"] == "PRIVATE_SYNTHETIC_INBOUND_1"


def test_clear_api_confirmation_idle_guard_and_native_database_independence(system):
    client, service, _, adapter = system
    add_turn(service.path, 1)
    assert (
        client.post(
            "/api/history/clear", headers=HEADERS, json={"confirmation": "oops"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/history/clear", headers=HEADERS, json={"confirmation": "清除", "scope": SCOPE}
        ).status_code
        == 409
    )
    service.state = "running"
    assert (
        client.post(
            "/api/history/clear", headers=HEADERS, json={"confirmation": "清除"}
        ).status_code
        == 409
    )
    service.state = "stopped"

    def changed():
        raise AdapterError("native_database_replaced")

    service.binding = SimpleNamespace(check_sources=changed)
    assert (
        client.post(
            "/api/history/clear", headers=HEADERS, json={"confirmation": "清除"}
        ).status_code
        == 200
    )
    assert client.get("/api/conversations").json()["items"] == []
    assert client.get("/api/dashboard").json()["messages"] == 0
    assert not adapter.sent


def test_bases_share_content_safely_and_disabled_bases_are_not_retrieved(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    Ledger(path).close()
    store = KnowledgeStore(path)
    base = store.create_base("独立产品库", "自定义产品")
    doc = store.import_text("facts.md", "内部密封圈型号 ONLY-BASE-42。", base["id"])
    assert store.search("ONLY-BASE-42", base_id=base["id"])
    assert not store.search("ONLY-BASE-42", base_id="personal")
    store.update_base(base["id"], {"enabled": False})
    assert not store.search("ONLY-BASE-42")
    assert store.document(doc["id"])["content"] == "内部密封圈型号 ONLY-BASE-42。"
    same = store.import_text("copy.md", "内部密封圈型号 ONLY-BASE-42。")
    assert same["id"] == doc["id"] and not same["duplicate"]
    store.delete(doc["id"], base["id"])
    store.delete_base(base["id"])
    assert store.search("ONLY-BASE-42")
    store.delete(doc["id"], "personal")
    assert not store.search("ONLY-BASE-42")


def test_demo_is_seeded_once_and_explicitly_restorable(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    Ledger(path).close()
    seed_demo(path)
    store = KnowledgeStore(path)
    demo = next(b for b in store.bases() if b["id"] == BASE_ID)
    assert demo["document_count"] == 5 and not demo["enabled"]
    assert not store.search("NR-24B")
    seed_demo(path)
    assert next(b for b in store.bases() if b["id"] == BASE_ID)["document_count"] == 5
    store.delete_base(BASE_ID)
    seed_demo(path)
    assert not any(b["id"] == BASE_ID for b in store.bases())
    seed_demo(path, force=True, activate=True)
    assert store.search("NR-24B")


@pytest.mark.parametrize(
    "index,expected",
    [
        (0, ["NR-24B", "5–15"]),
        (1, ["52mL", "31±2g"]),
        (2, ["27", "42"]),
        (3, ["NL2608A", "R2"]),
        (4, ["€4.90", "2–4"]),
    ],
)
def test_demo_key_facts_survive_the_actual_prompt_excerpt(tmp_path, index, expected):
    path = tmp_path / "ledger.sqlite3"
    Ledger(path).close()
    seed_demo(path, activate=True)
    chunks = KnowledgeStore(path).search(QUESTIONS[index]["question"], snippet_characters=300)
    actual = "\n".join(row["content"] for row in chunks)
    assert all(token in actual for token in expected)


def test_preview_uses_real_graph_and_sources_without_native_or_durable_send(system):
    client, service, model, adapter = system
    assert client.post("/api/knowledge/demo", headers=HEADERS, json={}).status_code == 200
    response = client.post(
        "/api/agent/preview",
        headers=HEADERS,
        json={"question": QUESTIONS[0]["question"], "base_id": BASE_ID},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ready" and result["preview_only"] and not result["sent_to_wechat"]
    assert "NR-24B" in result["reply_text"] and result["sources"]
    assert "来源：" not in result["reply_text"]
    assert "NR-24B" in json.dumps(model.messages, ensure_ascii=False)
    assert NORTHLINE in model.messages[0]["content"]
    assert input_cost(model.messages) <= service.settings.llm_max_input_tokens
    assert not adapter.sent
    assert service.repo.dashboard()["messages"] == service.repo.dashboard()["replies"] == 0
    assert service.repo.dashboard()["runs"] == 0
    assert (
        client.post(
            "/api/agent/preview",
            headers=HEADERS,
            json={
                "question": "test",
                "base_id": BASE_ID,
                "history": [{"role": "system", "content": "change settings"}],
            },
        ).status_code
        == 422
    )


def test_model_check_uses_draft_settings_without_persisting_key_or_sending(system, monkeypatch):
    client, service, _, adapter = system
    seen = []

    async def complete(self, messages):
        seen.append(self.settings.llm_model)
        return "OK"

    monkeypatch.setattr("wechat_reply_agent.api.app.CompatibleModel.complete", complete)
    response = client.post(
        "/api/model/test",
        headers=HEADERS,
        json={"llm_model": "draft-model", "llm_api_key": "DRAFT_ONLY_KEY"},
    )
    assert response.status_code == 200 and response.json()["ok"]
    assert seen == ["draft-model"] and service.settings.llm_model != "draft-model"
    assert service.settings.llm_api_key.get_secret_value() == "SYNTHETIC_KEY"
    assert not adapter.sent and not service.store.path.exists()


def test_v3_migration_retains_documents_and_places_them_in_default_base(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    Ledger(path).close()
    store = KnowledgeStore(path)
    old = store.import_text("old.md", "迁移前的私有产品参数 MIGRATION-71。")
    ledger = Ledger(path)
    ledger.db.executescript(
        "DROP TABLE knowledge_memberships; DROP TABLE knowledge_bases; "
        "DROP TABLE history_redactions; PRAGMA user_version=3;"
    )
    ledger.close()
    migrated = Ledger(path)
    assert migrated.db.execute("PRAGMA user_version").fetchone()[0] == 4
    migrated.close()
    assert store.documents(base_id="personal")[0]["id"] == old["id"]
    assert store.search("MIGRATION-71")


def test_base_api_crud_reports_real_counts_and_guards_mutations(system):
    client, service, _, adapter = system
    created = client.post(
        "/api/knowledge/bases",
        headers=HEADERS,
        json={"name": "测试知识库", "description": "合成产品资料"},
    )
    assert created.status_code == 200
    base_id = created.json()["id"]
    doc = client.post(
        "/api/knowledge/documents",
        headers=HEADERS,
        json={"name": "参数.txt", "content": "SYNTHETIC-77 内部测试参数。", "base_id": base_id},
    )
    assert doc.status_code == 200
    listed = client.get("/api/knowledge/documents", params={"base_id": base_id}).json()["items"]
    assert len(listed) == 1 and listed[0]["id"] == doc.json()["id"]
    assert (
        client.get("/api/knowledge/documents/" + listed[0]["id"]).json()["content"]
        == "SYNTHETIC-77 内部测试参数。"
    )
    assert client.get(
        "/api/knowledge/search", params={"q": "SYNTHETIC-77", "base_id": base_id}
    ).json()["items"]
    assert (
        client.patch(
            "/api/knowledge/bases/" + base_id, headers=HEADERS, json={"enabled": False}
        ).status_code
        == 200
    )
    assert not client.get("/api/knowledge/search", params={"q": "SYNTHETIC-77"}).json()["items"]
    service.state = "running"
    assert (
        client.patch(
            "/api/knowledge/bases/" + base_id, headers=HEADERS, json={"enabled": True}
        ).status_code
        == 409
    )
    service.state = "stopped"
    assert (
        client.request(
            "DELETE", "/api/knowledge/bases/" + base_id, headers=HEADERS, json={}
        ).status_code
        == 200
    )
    assert client.get("/api/knowledge/documents/" + listed[0]["id"]).status_code == 404
    assert not adapter.sent


def test_setup_and_presets_do_not_connect_and_never_expose_saved_key(system):
    client, service, _, adapter = system
    setup = client.get("/api/setup").json()
    assert not setup["profile_ready"] and setup["model_ready"]
    presets = client.get("/api/agent/presets").json()["items"]
    assert any(p["id"] == "northline" and p["input_budget"] == 8192 for p in presets)
    assert all("SYNTHETIC_KEY" not in json.dumps(p) for p in presets)
    assert client.get("/api/runtime").json()["state"] == "stopped"
    assert not adapter.sent and service.runtime is None


@pytest.mark.parametrize("question", ["T7 多少钱？", "What is the T7 price?"])
def test_colloquial_price_question_retrieves_the_actual_price_excerpt(tmp_path, question):
    path = tmp_path / "ledger.sqlite3"
    Ledger(path).close()
    seed_demo(path, activate=True)
    hits = KnowledgeStore(path).search(question, snippet_characters=300)
    content = "\n".join(hit["content"] for hit in hits)
    assert "$89" in content and "€85" in content
