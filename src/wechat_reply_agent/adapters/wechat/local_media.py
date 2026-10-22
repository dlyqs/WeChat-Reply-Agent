"""Local-only media acquisition. No UI, network download, playback or transcription."""

import hashlib
import os
import re
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import LocalAttachment
from wechat_reply_agent.privacy import private_directory


def file_info(content):
    """Extract just file metadata; never retain XML containing download credentials."""
    if isinstance(content, bytes):
        try:
            if content.startswith(b"\x28\xb5\x2f\xfd"):
                import zstandard

                content = zstandard.ZstdDecompressor().decompress(
                    content, max_output_size=4 * 1024**2
                )
            content = content.decode("utf-8", "replace")
        except Exception:
            return {}
    if not isinstance(content, str) or len(content) > 4 * 1024**2:
        return {}
    # Do not expand DTDs/entities in received content.
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        return {}
    try:
        root = ET.fromstring(content)
        app = root if root.tag == "appmsg" else root.find(".//appmsg")
        if app is None or app.findtext("type") != "6":
            return {}
        size = app.findtext("appattach/totallen")
        md5 = (
            app.findtext("appattach/filemd5")
            or app.findtext("appattach/md5")
            or app.findtext("md5")
        )
        return {
            "kind": "file",
            "name": safe_name(app.findtext("title")),
            "byte_size": int(size) if size and size.isdigit() else None,
            "md5": md5.lower() if md5 and re.fullmatch(r"[a-fA-F0-9]{32}", md5) else None,
        }
    except (ET.ParseError, ValueError):
        return {}


def safe_name(value):
    if not isinstance(value, str):
        return None
    name = value.strip()
    if (
        not name
        or name in (".", "..")
        or len(name) > 240
        or any(c in name for c in '/\\:<>"|?*')
        or any(ord(c) < 32 for c in name)
    ):
        return None
    return name


def describe_media(row):
    code = row.get("local_type", row.get("type_code", 0))
    code = int(code) if str(code).isdigit() else 0
    kind = code & 0xFFFFFFFF
    if kind == 34 or row.get("type") in ("语音", "voice", 34):
        return LocalAttachment(kind="voice", name="语音.silk", format="silk")
    if kind == 49 or row.get("type") in ("文件/链接/卡片", "file", 49):
        info = file_info(row.get("content"))
        if row.get("media_kind") == "file":
            info = {"name": safe_name(row.get("file_name")), "byte_size": row.get("file_size")}
        if info or code >> 32 == 6:
            return LocalAttachment(
                kind="file", name=info.get("name"), byte_size=info.get("byte_size")
            )
    return None


def attachment_directory(data_dir, event_id):
    # Both directory components are application-owned, never native names or API paths.
    root = data_dir.resolve() / "attachments"
    directory = root / hashlib.sha256(event_id.encode()).hexdigest()
    if root.is_symlink() or directory.is_symlink():
        raise AdapterError("attachment_location_rejected")
    return directory


def local_file(account_root, name, created_at, expected_size=None, expected_md5=None):
    """Prefer the message's month. Never choose arbitrarily among duplicate filenames."""
    name = safe_name(name)
    root = account_root / "msg/file"
    if not name or not root.is_dir() or root.is_symlink():
        return None, "not_downloaded"
    root = root.resolve()
    filename = Path(name)
    numbered_name = re.compile(
        re.escape(filename.stem) + r" ?\([1-9][0-9]*\)" + re.escape(filename.suffix)
    )

    def matches_name(candidate):
        if candidate.name == name:
            return True
        # WeChat/macOS/Windows may add a counter when saving the same filename again.
        # A renamed candidate must also have independently supplied size or MD5 metadata.
        return (expected_size is not None or expected_md5 is not None) and bool(
            numbered_name.fullmatch(candidate.name)
        )

    # Search inside this account only, and ignore links escaping the media directory.
    candidates = [
        p
        for p in root.rglob("*")
        if matches_name(p)
        and p.is_file()
        and not p.is_symlink()
        and p.resolve().is_relative_to(root)
        and (expected_size is None or p.stat().st_size == expected_size)
    ]
    if created_at:
        # Native timestamps are seconds. Check UTC and local month at timezone boundaries.
        months = {
            datetime.fromtimestamp(created_at, UTC).strftime("%Y-%m"),
            datetime.fromtimestamp(created_at).strftime("%Y-%m"),
        }
        candidates = [
            p
            for p in candidates
            if (
                months.intersection(p.relative_to(root).parts[:-1])
                or not any(
                    re.fullmatch(r"\d{4}-\d{2}", part) for part in p.relative_to(root).parts[:-1]
                )
            )
        ]
    if expected_md5:
        matching = []
        for candidate in candidates:
            with candidate.open("rb") as content:
                if hashlib.file_digest(content, "md5").hexdigest() == expected_md5:
                    matching.append(candidate)
        candidates = matching
    if len(candidates) != 1:
        return None, "ambiguous_file" if candidates else "not_downloaded"
    return candidates[0], None


def copy_local_file(source, directory, name):
    private_directory(directory.parent)
    private_directory(directory)
    target = directory / safe_name(name)
    before = source.stat()
    fd, tmp = tempfile.mkstemp(prefix=".acquiring-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, output)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("file_still_downloading")
        os.replace(tmp, target)
        return target
    finally:
        Path(tmp).unlink(missing_ok=True)


def result(event, path=None, reason=None, error=False, name=None):
    info = event.attachment.model_copy(
        update={
            "status": "available" if path else "error" if error else "missing",
            "reason": reason,
            "checked_at": time.time(),
            "name": name or (path.name if path else event.attachment.name),
            "byte_size": path.stat().st_size if path else event.attachment.byte_size,
        }
    )
    return info, str(path.resolve()) if path else None


class ReplicaLocalMedia:
    def __init__(self, db, data_dir):
        self.db, self.data_dir = db, data_dir

    def acquire(self, event):
        from wechatauto.media import MediaDownloader

        directory = attachment_directory(self.data_dir, event.event_id)
        # Read back the exact shard; local_id is not globally unique.
        row = self.db.get_message_row(event.conversation_id, event.local_id, shard=event.shard)
        if not row or (int(row["local_type"]) & 0xFFFFFFFF) != (
            34 if event.type == "voice" else 49
        ):
            return result(event, reason="message_missing")
        directory_parent = directory

        class Downloader(MediaDownloader):
            def _out(self, save_dir, filename):
                # Ignore upstream's native-username based filename.
                private_directory(directory_parent.parent)
                private_directory(directory_parent)
                fd, temp = tempfile.mkstemp(prefix=".voice-", dir=directory_parent)
                os.close(fd)
                return temp

        downloader = Downloader(self.db, save_dir=str(directory))
        if event.type == "voice":
            path = downloader.download_voice(
                event.conversation_id, event.local_id, str(directory), shard=event.shard
            )
            if not path:
                return result(event, reason="not_downloaded")
            source = Path(path)
            try:
                with source.open("rb") as audio:
                    header = audio.read(10)
                if not (header.startswith(b"#!SILK_V3") or header.startswith(b"\x02#!SILK_V3")):
                    return result(event, reason="unsupported_audio", error=True)
                target = copy_local_file(source, directory, "语音.silk")
            finally:
                source.unlink(missing_ok=True)
            return result(event, target)
        info = file_info(row.get("content"))
        name = info.get("name") or safe_name(downloader._file_name(row))
        size = info.get("byte_size", event.attachment.byte_size)
        source, reason = local_file(
            Path(self.db.account_dir), name, row.get("create_time"), size, info.get("md5")
        )
        if not source:
            return result(event, reason=reason, name=name)
        return result(event, copy_local_file(source, directory, name))


def literal(value):
    return "CAST(x'" + str(value).encode().hex() + "' AS TEXT)"


class MacLocalMedia:
    def __init__(self, reader, data_dir):
        self.reader, self.data_dir = reader, data_dir

    def message(self, event):
        paths = [
            (p, t) for p, t in self.reader.paths(event.conversation_id) if p.name == event.shard
        ]
        if len(paths) != 1 or not event.local_id or event.local_id < 1:
            return None
        path, table = paths[0]
        with self.reader.open(path) as db:
            rows = db.query(
                f"SELECT server_id,local_type,create_time,hex(message_content) AS body "
                f'FROM "{table}" WHERE local_id={int(event.local_id)}'
            )
        return rows[0] if len(rows) == 1 else None

    def acquire(self, event):
        row = self.message(event)
        if not row or (int(row["local_type"]) & 0xFFFFFFFF) != (
            34 if event.type == "voice" else 49
        ):
            return result(event, reason="message_missing")
        server = int(row["server_id"] or 0)
        if not server:
            return result(event, reason="message_missing")
        directory = attachment_directory(self.data_dir, event.event_id)
        if event.type == "voice":
            return self.voice(event, server, directory)
        info = file_info(bytes.fromhex(row["body"] or ""))
        name, size = info.get("name"), info.get("byte_size")
        resource = self.reader.root / "message/message_resource.db"
        if not name and resource.is_file():
            with self.reader.open(resource) as db:
                rows = db.query(
                    "SELECT hex(d.packed_info) AS name,d.size FROM MessageResourceDetail d "
                    "JOIN MessageResourceInfo i ON d.message_id=i.message_id "
                    f"WHERE i.message_svr_id={server} AND i.message_local_id={int(event.local_id)} "
                    "AND i.chat_id IN (SELECT rowid FROM ChatName2Id WHERE user_name="
                    + literal(event.conversation_id)
                    + ")"
                )
            if not name:
                names = {
                    safe_name(bytes.fromhex(r["name"] or "").decode("utf-8", "replace"))
                    for r in rows
                }
                names.discard(None)
                if len(names) == 1:
                    name = names.pop()
            if size is None and len(rows) == 1 and rows[0]["size"]:
                size = int(rows[0]["size"])
        source, reason = local_file(
            self.reader.root.parent, name, int(row["create_time"]), size, info.get("md5")
        )
        if not source:
            return result(event, reason=reason, name=name)
        return result(event, copy_local_file(source, directory, name))

    def voice(self, event, server, directory):
        # WeChat 4.x uses VoiceInfo/Name2Id. Discover media shards under db_storage only.
        failed = False
        for path in sorted(self.reader.root.rglob("media_*.db")):
            if (
                not re.fullmatch(r"media_[0-9]+\.db", path.name)
                or path.is_symlink()
                or not path.resolve().is_relative_to(self.reader.root.resolve())
            ):
                continue
            try:
                with self.reader.open(path) as db:
                    rows = db.query(
                        "SELECT hex(voice_data) AS audio FROM VoiceInfo "
                        f"WHERE svr_id={server} AND chat_name_id IN "
                        "(SELECT rowid FROM Name2Id WHERE user_name="
                        + literal(event.conversation_id)
                        + ") ORDER BY create_time DESC LIMIT 1"
                    )
                if not rows or not rows[0]["audio"]:
                    continue
                audio = bytes.fromhex(rows[0]["audio"])
                if not (audio.startswith(b"#!SILK_V3") or audio.startswith(b"\x02#!SILK_V3")):
                    return result(event, reason="unsupported_audio", error=True)
                private_directory(directory.parent)
                private_directory(directory)
                fd, temp = tempfile.mkstemp(prefix=".voice-", dir=directory)
                try:
                    with os.fdopen(fd, "wb") as output:
                        output.write(audio)
                    target = directory / "语音.silk"
                    os.replace(temp, target)
                finally:
                    Path(temp).unlink(missing_ok=True)
                return result(event, target)
            except Exception:
                failed = True
        return result(
            event, reason="media_read_failed" if failed else "not_downloaded", error=failed
        )
