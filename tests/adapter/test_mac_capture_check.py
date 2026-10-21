"""Capture diagnostics cannot pass on exit status alone or overwrite evidence."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/acceptance/mac_capture_check.py"
spec = importlib.util.spec_from_file_location("mac_capture_check", SCRIPT)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


@pytest.mark.parametrize("backend", ["display", "picker"])
def test_native_zero_without_verified_frames_does_not_pass_gate(tmp_path, monkeypatch, backend):
    settings = SimpleNamespace(wechat_adapter="mac_db", data_dir=tmp_path)
    gate = tmp_path / "g1.json"
    gate.write_text('{"g1":"failed"}')
    binary = tmp_path / "bridge"
    binary.write_bytes(b"synthetic")
    import hashlib

    binary.with_suffix(".build.json").write_text(
        json.dumps({"binary": hashlib.sha256(binary.read_bytes()).hexdigest(), "sources": {}})
    )
    actions = []
    adapter = SimpleNamespace(
        connect=lambda: actions.append("connect"),
        close=lambda: actions.append("close"),
        profile=SimpleNamespace(contacts=[SimpleNamespace(title="private friend")]),
        _bridge=SimpleNamespace(process={"pid": 123}),
    )
    monkeypatch.setattr(capture, "create_adapter", lambda *a, **k: adapter)
    monkeypatch.setattr(capture, "context", lambda p: {"plan_version": "v5"})
    monkeypatch.setattr(capture, "bridge_path", lambda s: binary)
    board = SimpleNamespace(changeCount=lambda: 1)
    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(NSPasteboard=SimpleNamespace(generalPasteboard=lambda: board)),
    )

    def native(command, **kwargs):
        assert "send" not in command and "focus" not in command
        event = {"type": "capture_recording_finished", "title_verified": False}
        return SimpleNamespace(returncode=0, stdout=json.dumps(event))

    monkeypatch.setattr(capture.subprocess, "run", native)
    output = tmp_path / "capture.json"
    assert capture.check_capture(settings, mode="independent", backend=backend, output=output) == 2
    report = json.loads(output.read_text())
    assert report["status"] == "failed" and report["input_events"] == 0
    assert actions == ["connect", "close"] and gate.read_text() == '{"g1":"failed"}'


@pytest.mark.parametrize("outside", [False, True])
def test_capture_refuses_overwrite_or_public_output_before_native_work(
    tmp_path, monkeypatch, outside
):
    settings = SimpleNamespace(wechat_adapter="mac_db", data_dir=tmp_path / "private")
    settings.data_dir.mkdir()
    output = (tmp_path if outside else settings.data_dir) / "capture.json"
    output.write_text("preserve existing evidence")

    def forbidden(*a, **k):
        raise AssertionError("no native calls allowed")

    monkeypatch.setattr(capture, "create_adapter", forbidden)
    with pytest.raises(AdapterError, match="capture_output_"):
        capture.check_capture(settings, mode="independent", backend="display", output=output)
    assert output.read_text() == "preserve existing evidence"
