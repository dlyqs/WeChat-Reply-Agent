"""Private storage permissions, without importing a desktop library."""

import csv
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError


@lru_cache(maxsize=1)
def current_sid():
    result = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True
    )
    sid = next(csv.reader([result.stdout.strip()]))[1]
    if not sid.startswith("S-1-"):
        raise AdapterError("private_acl_unavailable")
    return sid


def private_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "nt":
        sid = current_sid()
        reset = subprocess.run(["icacls", str(path.resolve()), "/reset"], capture_output=True)
        if reset.returncode:
            raise AdapterError("private_acl_failed")
        # Remove inherited grants and set current-user ownership/access. No shell expansion.
        result = subprocess.run(
            ["icacls", str(path.resolve()), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"],
            capture_output=True,
        )
        if result.returncode:
            raise AdapterError("private_acl_failed")
    else:
        path.chmod(0o700)
