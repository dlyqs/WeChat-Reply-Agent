import pytest
from pydantic import ValidationError

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.fake import FakeAdapter
from wechat_reply_agent.adapters.wechat.mac_ax import classify_direction
from wechat_reply_agent.adapters.wechat.profile import AXProfile, load_profile
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import ConversationRef, Direction, InboundEvent, SendIntent

from .conftest import Pixels


def test_safe_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.send_mode == "dry-run" and settings.wechat_allowlist == []


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    path = tmp_path / "sample.env"
    path.write_text('SEND_MODE=live\nWECHAT_ALLOWLIST=["a"]\n')
    monkeypatch.setenv("SEND_MODE", "dry-run")
    assert Settings(_env_file=path).send_mode == "dry-run"


@pytest.mark.parametrize("aliases", [["a", "a"], [""], [" a"]])
def test_invalid_allowlist(aliases):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, wechat_allowlist=aliases)


def test_unknown_identity_cannot_make_intent():
    ref = ConversationRef(
        account_ref="a",
        conversation_id="local-c",
        contact_alias="c",
        profile="test",
        identity_basis="unknown",
        confidence=0,
    )
    with pytest.raises(ValidationError):
        SendIntent(conversation=ref, reply_text="hello")
    with pytest.raises(AdapterError):
        FakeAdapter([ref]).resolve_conversation("c")


def test_complete_event_contract():
    event = InboundEvent(
        conversation_id="local-c",
        occurrence_ref="frame:1",
        direction=Direction.UNKNOWN,
        confidence=0,
    )
    assert event.event_id and event.trace_id and event.observed_at.tzinfo
    assert event.source_message_id is None and event.direction == "unknown"
    with pytest.raises(ValidationError):
        InboundEvent(conversation_id="x", occurrence_ref="x", direction="guessed", confidence=2)


@pytest.mark.parametrize("field", ["alias", "title", "local_conversation_id"])
def test_profile_rejects_duplicate_binding(field):
    a = {"alias": "a", "title": "A", "local_conversation_id": "1"}
    b = {"alias": "b", "title": "B", "local_conversation_id": "2"}
    b[field] = a[field]
    with pytest.raises(ValidationError):
        AXProfile(
            account_ref="a",
            wechat_version="test",
            distribution="test",
            language="en",
            contacts=[a, b],
        )


def test_missing_profile_sanitized(tmp_path):
    with pytest.raises(AdapterError, match="profile_missing_or_invalid"):
        load_profile(tmp_path / "missing")


@pytest.mark.parametrize(
    ("side", "expected"),
    [("both", "unknown"), ("neither", "unknown"), ("left", "incoming"), ("right", "outgoing")],
)
def test_heuristic_direction(side, expected):
    assert classify_direction(Pixels(side), (0, 0), (0, 0), (120, 40)) == expected
