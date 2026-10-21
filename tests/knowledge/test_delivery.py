import hashlib
import json
import zipfile

import pytest

from wechat_reply_agent.acceptance.delivery import REQUIRED, package, verify
from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.cli import main


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    for name in REQUIRED:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}" if name.endswith(".json") else "synthetic source\n")
    assets = root / "src/wechat_reply_agent/web/assets/app.js"
    assets.parent.mkdir(parents=True)
    assets.write_text("synthetic bundled UI")
    (root / "pyproject.toml").write_text(
        '[tool.uv.sources]\nwechatauto-replica = {path="third_party/wechatauto_replica"}\n'
    )
    (root / "src/wechat_reply_agent/web/index.html").write_text(
        '<script src="/assets/app.js"></script>'
    )
    return root


def test_draft_archive_hashes_privacy_exclusions_and_pending_gates(source, tmp_path):
    for name in (
        ".env",
        ".local/private-chat.txt",
        "ui/node_modules/secret.txt",
        "src/private.sqlite3",
        "ui/.env.local",
        "third_party/wechat_mac_toolkit/wechat-ui",
    ):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("MUST_NOT_BE_EXPORTED")
    output = tmp_path / "draft.zip"
    report = package(source, output, draft=True)
    assert report["source_status"] == "passed" and report["delivery_status"] == "pending_acceptance"
    assert report["kind"] == "source_draft"
    with zipfile.ZipFile(output) as archive:
        assert not any(b"MUST_NOT_BE_EXPORTED" in archive.read(n) for n in archive.namelist())
        manifest = json.loads(archive.read("wechat-reply-agent/delivery-manifest.json"))
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read("wechat-reply-agent/" + name)).hexdigest() == digest
    with pytest.raises(AdapterError, match="delivery_output_exists"):
        package(source, output, draft=True)
    with pytest.raises(AdapterError, match="delivery_human_acceptance_pending"):
        package(source, tmp_path / "final.zip")
    assert not (tmp_path / "final.zip").exists()


def test_missing_source_secret_and_symlink_are_rejected(source, tmp_path):
    (source / "LICENSE").unlink()
    assert verify(source)["source_status"] == "failed"
    (source / "LICENSE").write_text("synthetic")
    secret = source / "docs/accidental.txt"
    secret.write_text("sk-" + "x" * 30)
    with pytest.raises(AdapterError, match="delivery_secret_pattern_detected"):
        package(source, tmp_path / "rejected.zip", draft=True)
    secret.unlink()
    target = tmp_path / "outside.txt"
    target.write_text("private")
    try:
        secret.symlink_to(target)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    with pytest.raises(AdapterError, match="delivery_symlink_rejected"):
        package(source, tmp_path / "rejected.zip", draft=True)


def test_rejected_final_cli_never_writes_json_into_zip(source, tmp_path):
    output = tmp_path / "final.zip"
    assert main(["package", "--root", str(source), "--output", str(output)]) == 2
    assert not output.exists()
