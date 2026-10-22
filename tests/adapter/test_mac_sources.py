"""Legacy acceptance stays valid only for exact old DB identities plus new media shards."""

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import MacBridge, source_identity
from wechat_reply_agent.adapters.wechat.mac_sources import (
    extends_with_media,
    matching_accepted_sources,
    source_fingerprint,
)
from wechat_reply_agent.config import Settings


@pytest.mark.parametrize("mutation", ["addition", "replacement", "deletion", "non_media_addition"])
def test_media_additions_cannot_mask_accepted_database_changes(mutation):
    accepted = {"message/message_0.db": [1, 2, "salt"], "message/media_0.db": [1, 3, "audio"]}
    current = accepted | {"message/media_1.db": [1, 4, "new audio"]}
    if mutation == "replacement":
        current["message/media_0.db"] = [1, 9, "other audio"]
    elif mutation == "deletion":
        del current["message/media_0.db"]
    elif mutation == "non_media_addition":
        current["message/message_1.db"] = [1, 9, "other messages"]
    matching = matching_accepted_sources(current, source_fingerprint(accepted))
    if mutation == "addition":
        assert matching == accepted and extends_with_media(accepted, current)
    else:
        assert matching is None and not extends_with_media(accepted, current)


def test_bridge_pins_added_media_and_rejects_its_subsequent_replacement(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from wechat_reply_agent.adapters.wechat import mac_bridge

    root = tmp_path / "db_storage"
    (root / "message").mkdir(parents=True)
    (root / "message/message_0.db").write_bytes(b"message identity")
    profile = SimpleNamespace(
        db_root=root, app_path=tmp_path / "app", wechat_version="synthetic", wechat_build="1"
    )
    bridge = MacBridge(Settings(_env_file=None, data_dir=tmp_path), profile)
    bridge.identity = source_identity(root)
    bridge.process = {"pid": 1}
    monkeypatch.setattr(mac_bridge, "process_binding", lambda *a: {"pid": 1})
    monkeypatch.setattr(mac_bridge, "client_version", lambda *a: ("synthetic", "1"))
    media = root / "message/media_0.db"
    media.write_bytes(b"first media salt")
    bridge.check()
    assert "message/media_0.db" in bridge.identity
    media.write_bytes(b"other media salt")
    with pytest.raises(AdapterError, match="native_database_replaced"):
        bridge.check()
