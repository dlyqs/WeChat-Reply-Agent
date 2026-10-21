import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

probe = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/probes/windows_read.py"))
ProbeError = probe["ProbeError"]


class Chat:
    def __init__(self, *, title="test", kind="friend", after_title=None, messages=()):
        self.title = title
        self.kind = kind
        self.after_title = after_title
        self.messages = list(messages)
        self.reads = 0

    def ChatInfo(self):
        title = self.after_title if self.reads and self.after_title else self.title
        return {"chat_name": title, "chat_type": self.kind}

    def GetAllMessage(self):
        self.reads += 1
        return self.messages


@pytest.mark.parametrize("chat", [Chat(title="other"), Chat(kind="group")])
def test_wrong_target_is_rejected_before_reading(chat):
    with pytest.raises(ProbeError):
        probe["read_snapshot"](chat, "test", 20)
    assert chat.reads == 0


def test_chat_changed_during_read_is_rejected():
    with pytest.raises(ProbeError, match="current_chat_mismatch"):
        probe["read_snapshot"](Chat(after_title="other"), "test", 20)


def test_repeated_text_stays_separate_and_direction_is_explicit():
    messages = [
        SimpleNamespace(type="text", content="same", attr="friend", id="1"),
        SimpleNamespace(type="text", content="same", attr="friend", id="2"),
        SimpleNamespace(type="text", content="reply", attr="self", id="3"),
        SimpleNamespace(type="text", content="uncertain", attr="other", id="4"),
        SimpleNamespace(type="image", content="image placeholder", attr="friend", id="5"),
    ]
    report = probe["read_snapshot"](Chat(messages=messages), "test", 20)
    assert [m["ui_id"] for m in report["messages"]] == ["1", "2", "3", "4"]
    assert [m["direction"] for m in report["messages"]] == [
        "incoming",
        "incoming",
        "outgoing",
        "unknown",
    ]
    assert report["g1"] == "not_tested"
    assert report["sending"] is False


def test_profile_without_confirmation_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps({"expected_chat_title": "test"}), encoding="utf-8")
    monkeypatch.setitem(probe["load_binding"].__globals__, "private_path", lambda p: p)
    with pytest.raises(ProbeError, match="test_binding_not_confirmed"):
        probe["load_binding"](path)


def test_private_output_cannot_escape_ignored_directory(tmp_path):
    with pytest.raises(ProbeError, match="path_must_be_under_local"):
        probe["write_report"](tmp_path / "report.json", {"messages": []})
    assert not (tmp_path / "report.json").exists()
