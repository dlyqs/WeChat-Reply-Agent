"""Local media identity, metadata and filesystem boundaries without desktop automation."""

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.local_media import (
    attachment_directory,
    describe_media,
    file_info,
    local_file,
)
from wechat_reply_agent.adapters.wechat.mac_db import MacAdapter
from wechat_reply_agent.adapters.wechat.replica import ReplicaAdapter

FILE_XML = (
    "<msg><appmsg><title>订单.pdf</title><type>6</type>"
    "<appattach><totallen>4</totallen><aeskey>PRIVATE</aeskey></appattach></appmsg></msg>"
)


@pytest.mark.parametrize("platform", ["windows", "mac"])
@pytest.mark.parametrize("kind", ["file", "voice", "link"])
def test_normalization_preserves_media_but_never_xml(platform, kind):
    profile = SimpleNamespace(account_generation="g1", account_ref="account", self_username="self")
    ref = SimpleNamespace(conversation_id="friend")
    code = {"file": 6 << 32 | 49, "voice": 34, "link": 5 << 32 | 49}[kind]
    row = dict(local_id=1, sort_seq=1, create_time=1, sender_id="friend", sender_username="friend")
    if platform == "windows":
        row.update(
            shard="db0",
            type_code=code,
            type="语音" if kind == "voice" else "文件/链接/卡片",
            content=FILE_XML if kind == "file" else "<msg><appmsg><type>5</type></appmsg></msg>",
        )
        adapter = ReplicaAdapter(None, profile)
    else:
        row.update(
            database="db0",
            local_type=code,
            text=None,
            media_kind="file" if kind == "file" else None,
            file_name="订单.pdf",
            file_size=4,
        )
        adapter = MacAdapter(None, profile)
    event = adapter.normalize(ref, row)
    assert event.type == (kind if kind != "link" else "unknown")
    assert event.text is None
    assert "PRIVATE" not in event.model_dump_json()
    if kind != "link":
        assert event.attachment.kind == kind and event.attachment.status == "pending"


def test_file_metadata_does_not_expand_entities_or_confuse_cards():
    assert file_info(FILE_XML)["name"] == "订单.pdf"
    assert file_info('<!DOCTYPE x [<!ENTITY a "x">]><appmsg><type>6</type></appmsg>') == {}
    assert describe_media({"local_type": 49, "content": "<msg/>"}) is None
    assert file_info(b"\x28\xb5\x2f\xfdinvalid") == {}


def test_local_files_require_correct_month_size_and_unique_location(tmp_path):
    root = tmp_path / "msg/file"
    for month in ("2026-09", "2026-10"):
        (root / month).mkdir(parents=True)
        (root / month / "订单.pdf").write_bytes(b"data")
    created = datetime(2026, 10, 22, tzinfo=UTC).timestamp()
    selected, reason = local_file(tmp_path, "订单.pdf", created, 4)
    assert selected == root / "2026-10/订单.pdf" and reason is None
    digest = hashlib.md5(b"data").hexdigest()
    assert local_file(tmp_path, "订单.pdf", created, 4, digest)[0] == selected
    assert local_file(tmp_path, "订单.pdf", created, 4, "0" * 32)[0] is None
    assert local_file(tmp_path, "订单.pdf", created, 9) == (None, "not_downloaded")
    selected.unlink()
    assert local_file(tmp_path, "订单.pdf", created, 4) == (None, "not_downloaded")
    (root / "2026-10/a").mkdir()
    (root / "2026-10/b").mkdir()
    for folder in ("a", "b"):
        (root / f"2026-10/{folder}/订单.pdf").write_bytes(b"data")
    assert local_file(tmp_path, "订单.pdf", created, 4) == (None, "ambiguous_file")
    assert local_file(tmp_path, "../secret", created) == (None, "not_downloaded")


@pytest.mark.parametrize("saved_name", ["订单(1).pdf", "订单 (2).pdf"])
def test_wechat_numbered_filenames_require_metadata_and_unique_match(tmp_path, saved_name):
    root = tmp_path / "msg/file/2026-10"
    root.mkdir(parents=True)
    saved = root / saved_name
    saved.write_bytes(b"data")
    created = datetime(2026, 10, 22, tzinfo=UTC).timestamp()
    assert local_file(tmp_path, "订单.pdf", created, 4) == (saved, None)
    assert local_file(tmp_path, "订单.pdf", created, 9) == (None, "not_downloaded")
    assert local_file(tmp_path, "订单.pdf", created) == (None, "not_downloaded")
    assert local_file(tmp_path, "订单.pdf", created, expected_md5="0" * 32)[0] is None
    (root / "订单(3).pdf").write_bytes(b"data")
    assert local_file(tmp_path, "订单.pdf", created, 4) == (None, "ambiguous_file")


def test_media_paths_cannot_escape_through_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "secret.pdf"
    source.write_bytes(b"secret")
    root = tmp_path / "account/msg/file"
    root.mkdir(parents=True)
    (root / "secret.pdf").symlink_to(source)
    assert local_file(tmp_path / "account", "secret.pdf", None)[0] is None
    (tmp_path / "attachments").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AdapterError, match="attachment_location_rejected"):
        attachment_directory(tmp_path, "id")


def test_old_inbox_json_still_loads_without_media_fields():
    from wechat_reply_agent.domain.messages import InboundEvent

    old = dict(
        conversation_id="friend",
        occurrence_ref="1",
        direction="incoming",
        text="hello",
        confidence=1,
    )
    assert InboundEvent.model_validate_json(json.dumps(old)).attachment is None
