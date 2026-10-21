import json
import os
import stat

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.cli import execute, parser, probe_lock, write_private


def test_private_report(tmp_path):
    path = tmp_path / "private" / "report.json"
    write_private(path, {"test": True})
    assert json.loads(path.read_text()) == {"test": True}
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    else:
        import subprocess

        acl = subprocess.check_output(["icacls", str(path.parent)], text=True)
        assert "(OI)(CI)(F)" in acl
        assert "(I)" not in acl


def test_failed_replace_keeps_previous(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    write_private(path, {"old": True})

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("wechat_reply_agent.cli.os.replace", fail)
    with pytest.raises(OSError):
        write_private(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
    assert list(tmp_path.iterdir()) == [path]


def test_probe_single_instance(tmp_path):
    with probe_lock(tmp_path):
        with pytest.raises(AdapterError, match="another_probe_running"), probe_lock(tmp_path):
            pass


def test_cli_read(settings, adapter, tmp_path):
    output = tmp_path / "read.json"
    args = parser().parse_args(
        ["probe", "read", "--contact", "a", "--limit", "1", "--output", str(output)]
    )
    assert execute(args, settings, adapter) == 0
    report = json.loads(output.read_text())
    assert len(report["events"]) == 1 and report["g1"] == "not_tested"


def test_cli_send_needs_confirmation(settings, adapter, bridge):
    args = parser().parse_args(["probe", "send", "--contact", "a", "--text", "test"])
    with pytest.raises(AdapterError, match="explicit_confirm_send_required"):
        execute(args, settings, adapter)
    assert bridge.keys == bridge.writes == 0


def test_cli_send_receipt(settings, adapter, bridge, capsys):
    args = parser().parse_args(
        ["probe", "send", "--contact", "a", "--text", "PRIVATE-TEST", "--confirm-send"]
    )
    assert execute(args, settings, adapter) == 3
    reports = list((settings.data_dir / "probe-sends").glob("*.json"))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text())["outcome"] == "unknown"
    assert "PRIVATE-TEST" not in capsys.readouterr().out
    assert bridge.keys == 1


def test_help_and_import_never_load_native_desktop_modules():
    import subprocess
    import sys

    code = (
        "import sys; import wechat_reply_agent.cli as cli; "
        "cli.parser().format_help(); "
        "assert all(n not in sys.modules for n in ['AppKit', 'Quartz', 'ApplicationServices'])"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_native_bridge_is_lazy(settings):
    from wechat_reply_agent.adapters.wechat.mac_ax import MacAXAdapter

    adapter = MacAXAdapter(settings)
    assert adapter._bridge is None


def test_non_macos_diagnostic_is_offline(settings, monkeypatch):
    from wechat_reply_agent.adapters.wechat.mac_ax import MacAXAdapter

    monkeypatch.setattr(
        "wechat_reply_agent.adapters.wechat.mac_ax.platform.system", lambda: "Linux"
    )
    health = MacAXAdapter(settings).health()
    assert not health.healthy and health.reason == "macos_required"
