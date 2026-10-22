"""Locked clean-source install, native helper build and stopped HTTP API validation."""

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from wechat_reply_agent.cli import write_private
from wechat_reply_agent.config import Settings
from wechat_reply_agent.privacy import private_directory


def main(phase=6):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", type=Path, default=shutil.which("uv"))
    parser.add_argument(
        "--archive", type=Path, default=Path("dist/wechat_reply_agent-0.1.0.tar.gz")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if platform.system() not in ("Darwin", "Windows") or not args.uv:
        raise SystemExit("native_platform_and_uv_required")
    if args.output.exists():
        raise SystemExit("output_exists")
    private_directory(args.output)
    target = Path(tempfile.mkdtemp(prefix="source-", dir=args.output))
    if zipfile.is_zipfile(args.archive):
        with zipfile.ZipFile(args.archive) as archive:
            names = archive.namelist()
            assert names and not any(
                "/.local/" in n
                or n.endswith("/.env")
                or "/node_modules/" in n
                or PurePosixPath(n).is_absolute()
                or ".." in PurePosixPath(n).parts
                for n in names
            )
            assert not any(
                (entry.external_attr >> 16) & 0o170000 == 0o120000 for entry in archive.infolist()
            )
            archive.extractall(target)
    else:
        with tarfile.open(args.archive) as archive:
            names = archive.getnames()
            assert not any(
                "/.local/" in n or n.endswith("/.env") or "/node_modules/" in n for n in names
            )
            archive.extractall(target, filter="data")
    checkout = next(target.iterdir())
    env = os.environ.copy()
    for name in (*Settings.model_fields, "pythonpath", "virtual_env", "uv_project_environment"):
        env.pop(name.upper(), None)
    mac = platform.system() == "Darwin"
    extra, adapter = ("mac", "mac_db") if mac else ("windows", "replica")
    with (args.output / "install.log").open("w") as log:
        subprocess.run(
            [
                str(args.uv.resolve()),
                "sync",
                "--locked",
                "--extra",
                extra,
                "--python",
                sys._base_executable,
                "--no-python-downloads",
            ],
            cwd=checkout,
            env=env,
            stdout=log,
            stderr=log,
            check=True,
            timeout=180,
        )
    python = checkout / (".venv/bin/python" if mac else ".venv/Scripts/python.exe")
    subprocess.run(
        [str(python), "-m", "wechat_reply_agent.cli", "--help"],
        cwd=checkout,
        env=env,
        capture_output=True,
        check=True,
        timeout=15,
    )
    if mac:
        with (args.output / "native-build.log").open("w") as log:
            subprocess.run(
                [str(python), "scripts/build_mac_bridge.py"],
                cwd=checkout,
                env=env,
                stdout=log,
                stderr=log,
                check=True,
                timeout=150,
            )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env["WECHAT_ADAPTER"] = adapter
    base = f"http://127.0.0.1:{port}"
    with (args.output / "serve.log").open("w") as log:
        process = subprocess.Popen(
            [str(python), "-m", "wechat_reply_agent.cli", "serve", "--port", str(port)],
            cwd=checkout,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 25
            while True:
                try:
                    with urllib.request.urlopen(base + "/api/health", timeout=2) as response:
                        health = json.load(response)
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("clean_source_serve_failed") from None
                    time.sleep(0.1)
            assert health["foundation"] == adapter
            assert (
                health["runtime"]["state"] == "stopped" and health["runtime"]["mode"] == "dry-run"
            )
            with urllib.request.urlopen(base + "/") as response:
                assert b"root" in response.read()
            with urllib.request.urlopen(base + "/api/settings") as response:
                settings = json.load(response)
                assert settings["values"]["wechat_allowlist"] == []
                assert not settings["values"]["llm_api_key_configured"]
            if phase == 9:

                def content_request(path, method, body):
                    request = urllib.request.Request(
                        base + path,
                        data=json.dumps(body).encode(),
                        method=method,
                        headers={
                            "Origin": base,
                            "X-WeChat-Agent": "1",
                            "Content-Type": "application/json",
                        },
                    )
                    with urllib.request.urlopen(request) as response:
                        return json.load(response)

                doc = content_request(
                    "/api/knowledge/documents",
                    "POST",
                    {"name": "synthetic.md", "content": "桂花乌龙茶18元。"},
                )
                from urllib.parse import quote

                with urllib.request.urlopen(
                    base + "/api/knowledge/search?q=" + quote("乌龙茶")
                ) as response:
                    assert json.load(response)["items"]
                content_request("/api/knowledge/documents/" + doc["id"], "DELETE", {})
                with urllib.request.urlopen(base + "/api/memories/contacts") as response:
                    assert json.load(response)["items"] == []
                with urllib.request.urlopen(base + "/api/knowledge/bases") as response:
                    bases = json.load(response)
                    demo = next(b for b in bases["items"] if b["id"] == "northline-demo")
                    assert demo["document_count"] == 5 and not demo["enabled"]
                content_request("/api/knowledge/demo", "POST", {})
                with urllib.request.urlopen(base + "/api/knowledge/search?q=NR-24B") as response:
                    assert json.load(response)["items"]
            request = urllib.request.Request(
                base + "/api/diagnostics",
                data=b"{}",
                method="POST",
                headers={"Origin": base, "X-WeChat-Agent": "1", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                assert json.load(response)["foundation"] == adapter
        finally:
            process.terminate()
            process.wait(timeout=15)
    write_private(
        args.output / "report.json",
        {
            "phase": phase,
            "plan_version": "v5",
            "platform": "macOS" if mac else "Windows",
            "foundation": adapter,
            "status": "passed",
            "mode": "clean_source_no_account",
            "python": platform.python_version(),
            "architecture": platform.machine(),
            "system": platform.platform(),
            "native_build_self_test": "passed" if mac else "not_applicable",
            "http_stopped_dry_run_and_static_ui": "passed",
            "locked_install": "passed",
            "native_send": "not_tested",
            "ui_human_acceptance": "not_tested",
            "knowledge_memory_http": "passed" if phase == 9 else "not_tested",
            "builtin_knowledge_base_http": "passed" if phase == 9 else "not_tested",
        },
    )
    print("clean_source_install_native_build_and_stopped_http_passed")


if __name__ == "__main__":
    main()
