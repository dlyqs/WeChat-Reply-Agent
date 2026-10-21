"""Bind one explicit Mac account and exact native friend; never sends or takes keys."""

import argparse
from pathlib import Path
from uuid import uuid4

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import (
    client_version,
    process_binding,
    toolkit_module,
)
from wechat_reply_agent.adapters.wechat.mac_profile import MacContact, MacProfile
from wechat_reply_agent.cli import probe_lock, write_private
from wechat_reply_agent.config import Settings


def bind(args):
    settings = Settings()
    with probe_lock(settings.data_dir):
        if args.output.exists():
            raise AdapterError("profile_exists_refusing_overwrite")
        root = args.db_root.resolve(strict=True)
        if not args.key_file.resolve().is_relative_to(settings.data_dir.resolve()):
            raise AdapterError("mac_keys_must_be_in_private_data_dir")
        process_binding(args.app, root)
        reader_module = toolkit_module("wechat_db")
        reader = reader_module.Reader(root, args.key_file)
        literal = reader_module.literal
        with reader.open(root / "contact/contact.db") as db:
            rows = db.query(
                "SELECT username,nick_name,remark,alias FROM contact WHERE "
                + f"alias={literal(args.wechat_id)} OR username={literal(args.wechat_id)}"
            )
            titles = db.query("SELECT username,nick_name,remark FROM contact")
        if len(rows) != 1:
            raise AdapterError("unique_native_friend_required")
        friend = rows[0]
        title = friend["remark"] or friend["nick_name"]
        if (
            title != args.title
            or len([r for r in titles if (r["remark"] or r["nick_name"]) == title]) != 1
        ):
            raise AdapterError("unique_exact_contact_title_required")
        candidates = set()
        for path, _ in reader.paths(friend["username"]):
            with reader.open(path) as db:
                for row in db.query("SELECT user_name FROM Name2Id"):
                    name = row["user_name"]
                    if name and (
                        root.parent.name == name or root.parent.name.startswith(name + "_")
                    ):
                        candidates.add(name)
        if len(candidates) != 1:
            raise AdapterError("unique_self_username_required")
        self_id = candidates.pop()
        # Require the self mapping in every selected message shard.
        reader.read(friend["username"], 1, self_id=self_id)
        version, build = client_version(args.app)
        profile = MacProfile(
            account_ref=settings.wechat_account_ref,
            self_username=self_id,
            account_generation=uuid4().hex,
            db_root=root,
            key_file=args.key_file.resolve(),
            app_path=args.app.resolve(),
            wechat_version=version,
            wechat_build=build,
            account_confirmed=True,
            contacts=(
                MacContact(
                    alias=args.alias,
                    username=friend["username"],
                    title=title,
                    wechat_id=args.wechat_id,
                    single_chat_confirmed=True,
                ),
            ),
            composer_top=args.composer_top,
            send_key=args.send_key,
        )
        write_private(args.output, profile.model_dump(mode="json"))
        print("native_account_and_friend_bound_no_send")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--app", type=Path, default=Path("/Applications/WeChat.app"))
    parser.add_argument("--alias", required=True)
    parser.add_argument("--wechat-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--composer-top", type=float)
    parser.add_argument("--send-key", choices=("enter", "cmd-enter"), default="enter")
    parser.add_argument("--output", type=Path, required=True)
    try:
        bind(parser.parse_args())
    except AdapterError as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        raise SystemExit("mac_binding_failed_see_local_configuration") from None


if __name__ == "__main__":
    main()
