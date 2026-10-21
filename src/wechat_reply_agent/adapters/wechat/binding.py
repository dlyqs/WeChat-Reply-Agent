"""Private, platform-neutral identity contract. Never exposed through the API."""

from dataclasses import dataclass
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError


@dataclass(frozen=True)
class SourceFile:
    device: int
    inode: int
    header: bytes

    @classmethod
    def read(cls, path):
        stat = path.stat()
        with path.open("rb") as stream:
            return cls(stat.st_dev, stat.st_ino, stream.read(16))


@dataclass(frozen=True)
class BoundContact:
    alias: str
    username: str


@dataclass(frozen=True)
class RuntimeBinding:
    account_ref: str
    account_generation: str
    fingerprint: str
    contacts: tuple[BoundContact, ...]
    source_files: dict[Path, SourceFile]

    def check_sources(self):
        try:
            if any(SourceFile.read(path) != stamp for path, stamp in self.source_files.items()):
                raise ValueError
        except (OSError, ValueError):
            raise AdapterError("native_database_replaced") from None
