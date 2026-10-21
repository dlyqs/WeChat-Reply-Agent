"""Reproducible native arm64 bridge build; never launches or activates WeChat."""

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

from wechat_reply_agent.cli import write_private
from wechat_reply_agent.privacy import private_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/macos/bin/wechat-ui"))
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("native_apple_silicon_required")
    root = Path(__file__).resolve().parents[1] / "third_party/wechat_mac_toolkit"
    private_directory(args.output.parent)
    sources = [
        root / name
        for name in ("WeChatUI.swift", "Send.swift", "WindowCapture.swift", "DegradedSend.swift")
    ]
    command = [
        "/usr/bin/xcrun",
        "swiftc",
        "-parse-as-library",
        "-O",
        "-target",
        "arm64-apple-macosx14.0",
        *map(str, sources),
        "-o",
        str(args.output),
    ]
    subprocess.run(command, check=True, timeout=120)
    # Developer signature gives the helper a stable requirement across identical builds.
    subprocess.run(
        [
            "/usr/bin/codesign",
            "--force",
            "--sign",
            "-",
            "--identifier",
            "local.wechat-reply-agent.bridge",
            str(args.output),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(args.output.resolve()), "self-test"], check=True, timeout=10)
    write_private(
        args.output.with_suffix(".build.json"),
        {
            "architecture": "arm64",
            "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            "binary": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            "compiler": subprocess.check_output(
                ["/usr/bin/xcrun", "swiftc", "--version"], text=True
            ).strip(),
        },
    )
    print(json.dumps({"bridge_built": True, "output": str(args.output)}))


if __name__ == "__main__":
    main()
