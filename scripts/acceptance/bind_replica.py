"""Bind one explicitly supplied friend identifier; refuse ambiguous account/contact discovery.

Writes only the private profile; it never sends or constructs a GUI driver.
"""

import argparse
import json
from uuid import uuid4

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.replica_bridge import environment, quiet_native
from wechat_reply_agent.adapters.wechat.replica_profile import ReplicaContact, ReplicaProfile
from wechat_reply_agent.cli import probe_lock, write_private
from wechat_reply_agent.config import Settings
from wechat_reply_agent.privacy import private_directory


def bind(settings, alias, wechat_id):
    if settings.wechat_profile.exists():
        raise AdapterError("existing_profile_preserved")
    generation = str(uuid4())
    private = settings.data_dir.resolve() / "replica" / generation / "db"
    private_directory(private)
    with quiet_native():
        from wechatauto.db import WeChatDB, auto_detect_db_dir

        root = settings.wechat_db_root or auto_detect_db_dir()
        if not root:
            raise AdapterError("database_root_not_found")
        from pathlib import Path

        root = Path(root).resolve()
        accounts = [p.name for p in root.iterdir() if (p / "db_storage").is_dir()]
        if len(accounts) != 1:
            raise AdapterError("explicit_account_selection_required")
        db = WeChatDB(
            db_dir=str(root),
            account=accounts[0],
            keys_file=str(private / "keys.json"),
            workdir=str(private),
            strict_account=True,
        )
        identity = db.extract_master_key()
        if not identity or identity[2] != db.wxid:
            raise AdapterError("active_account_unverified")
        conn = db._contact_conn()
        if conn is None:
            raise AdapterError("contact_database_unavailable")
        try:
            hits = conn.execute(
                "SELECT username,nick_name,remark FROM contact WHERE username=? OR alias=?",
                (wechat_id, wechat_id),
            ).fetchall()
            if len(hits) != 1:
                raise AdapterError("friend_identifier_ambiguous_or_missing")
            row = hits[0]
            username = row["username"]
            title = row["remark"] or row["nick_name"]
            if not title or username.endswith("@chatroom") or username == db.wxid:
                raise AdapterError("single_friend_chat_required")
            collisions = conn.execute(
                "SELECT username FROM contact WHERE remark=? OR (remark='' AND nick_name=?)",
                (title, title),
            ).fetchall()
            if len(collisions) != 1 or collisions[0]["username"] != username:
                raise AdapterError("friend_title_ambiguous")
        finally:
            conn.close()
        profile = ReplicaProfile(
            account_ref=settings.wechat_account_ref,
            account=accounts[0],
            self_username=identity[2],
            account_generation=generation,
            db_root=root,
            account_confirmed=True,
            wechat_version=environment()["wechat_version"] or "unverified",
            contacts=(
                ReplicaContact(
                    alias=alias, username=username, title=title, single_chat_confirmed=True
                ),
            ),
        )
    write_private(settings.wechat_profile, profile.model_dump(mode="json"))
    return {
        "status": "bound",
        "account": "process_verified",
        "contacts": 1,
        "profile": str(settings.wechat_profile),
        "g1": "not_tested",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--wechat-id", required=True)
    args = parser.parse_args()
    try:
        settings = Settings()
        with probe_lock(settings.data_dir):
            result = bind(settings, args.alias, args.wechat_id)
        print(json.dumps(result))
        return 0
    except AdapterError as exc:
        print(json.dumps({"status": "failed", "code": str(exc)}))
    except Exception:
        print(json.dumps({"status": "failed", "code": "binding_native_failed"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
