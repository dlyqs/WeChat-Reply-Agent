"""Offline clean-source install and real HTTP smoke check; never connects WeChat."""

import json
import os
import platform
import re
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

from wechat_reply_agent.cli import write_private


def main():
    root = Path(__file__).resolve().parents[2]
    output = root / ".local/acceptance/phase-3"
    output.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="clean-source-", dir=output))
    archive = root / "dist/wechat_reply_agent-0.1.0.tar.gz"
    with tarfile.open(archive) as package:
        names = package.getnames()
        assert not any("node_modules" in name or "/.env" == name[-5:] for name in names)
        assert any("/web/assets/" in name for name in names)
        assert any("/ui/package-lock.json" in name for name in names)
        package.extractall(target, filter="data")
    checkout = next(target.iterdir())
    with (output / "install.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            ["uv", "sync", "--locked", "--extra", "windows"],
            cwd=checkout,
            stdout=log,
            stderr=log,
            check=True,
        )
    python = checkout / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    environment = os.environ.copy()
    # A copied source package has no private dotenv/profile/gates; do not inherit runtime settings.
    from wechat_reply_agent.config import Settings

    for field in Settings.model_fields:
        environment.pop(field.upper(), None)
    base = f"http://127.0.0.1:{port}"
    with (output / "serve.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(python), "-m", "wechat_reply_agent.cli", "serve", "--port", str(port)],
            cwd=checkout,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(base + "/api/health", timeout=2) as response:
                        health = json.load(response)
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("clean_source_serve_failed") from None
                    time.sleep(0.1)
            assert health["runtime"]["state"] == "stopped"
            assert health["runtime"]["mode"] == "dry-run"
            assert not health["runtime"]["connected"]
            with urllib.request.urlopen(base + "/") as response:
                html = response.read().decode()
            assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
            assert len(assets) >= 2
            for asset in assets:
                with urllib.request.urlopen(base + asset) as response:
                    assert response.status == 200
            with urllib.request.urlopen(base + "/api/settings") as response:
                settings = json.load(response)
            assert "llm_api_key" not in settings["values"]
            assert not settings["values"]["llm_api_key_configured"]
            request = urllib.request.Request(
                base + "/api/runtime/stop",
                data=b"{}",
                headers={"Origin": base, "X-WeChat-Agent": "1", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                assert json.load(response)["state"] == "stopped"
        finally:
            process.terminate()
            process.wait(timeout=10)
    write_private(
        output / "install-check.json",
        {
            "phase": 3,
            "environment": {"platform": platform.system(), "python": platform.python_version()},
            "plan_version": "v4",
            "foundation": "replica",
            "mode": "offline",
            "case": "P03-04/P04-04",
            "expected": "locked clean source install and bundled HTTP UI",
            "actual": "Locked Windows install; CLI served stopped/dry-run API, HTML and assets",
            "status": "passed",
            "evidence_ref": "install.log/serve.log",
            "native_connect": "not_tested",
            "ui_human_acceptance": "not_tested",
        },
    )
    print("clean_source_install_and_http_passed")


if __name__ == "__main__":
    main()
