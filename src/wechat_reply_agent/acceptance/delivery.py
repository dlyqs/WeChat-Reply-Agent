"""Allowlisted local source packages with hashes and explicit outstanding human gates."""

import hashlib
import json
import re
import shutil
import subprocess
import tomllib
import zipfile
from datetime import UTC, datetime

from wechat_reply_agent.adapters.wechat.base import AdapterError

ROOT_FILES = {
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    ".env.example",
    ".gitignore",
}
ROOT_DIRS = {"src", "ui", "docs", "scripts", "tests", "examples", "third_party"}
EXCLUDED_PARTS = {
    ".git",
    ".local",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".DS_Store",
    ".settings-private",
    "dist",
    "build",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".wal",
    ".log",
    ".dylib",
    ".dll",
    ".exe",
    ".pem",
    ".key",
    ".mp4",
    ".mov",
    ".webm",
}
REQUIRED = (
    "pyproject.toml",
    "uv.lock",
    "ui/package-lock.json",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "third_party/wechatauto_replica/LICENSE",
    "third_party/wechatauto_replica/pyproject.toml",
    "third_party/wechatauto_replica/UPSTREAM.md",
    "third_party/wechat_mac_toolkit/LICENSE",
    "third_party/wechat_mac_toolkit/UPSTREAM.md",
    "third_party/wechat_mac_toolkit/WeChatUI.swift",
    "third_party/wechat_mac_toolkit/DegradedSend.swift",
    "third_party/wechat_mac_toolkit/Send.swift",
    "third_party/wechat_mac_toolkit/WindowCapture.swift",
    "third_party/wechat_mac_toolkit/sqlcipher_probe.py",
    "third_party/wechat_mac_toolkit/wechat_db.py",
    "third_party/wechatauto_replica/UPSTREAM_FILES.json",
    "third_party/wechat_mac_toolkit/upstream-files.json",
    "scripts/build_mac_bridge.py",
    "src/wechat_reply_agent/web/index.html",
    "src/wechat_reply_agent/web/THIRD_PARTY_LICENSES.txt",
    "docs/demo-script.md",
    "docs/delivery-checklist.md",
    "docs/acceptance-summary.json",
    "examples/knowledge/fictional-tea-shop.md",
)
SECRET = re.compile(rb"(?:sk-[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def source_files(root):
    files = []
    for top in sorted(ROOT_FILES | ROOT_DIRS):
        path = root / top
        if path.is_symlink():
            raise AdapterError("delivery_symlink_rejected")
        candidates = path.rglob("*") if path.is_dir() else [path]
        for candidate in candidates:
            relative = candidate.relative_to(root)
            if any(part in EXCLUDED_PARTS or part.startswith("._") for part in relative.parts):
                continue
            if candidate.is_symlink():
                raise AdapterError("delivery_symlink_rejected")
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if candidate.name.startswith(".env") and candidate.name != ".env.example":
                continue
            if relative.as_posix() == "third_party/wechat_mac_toolkit/wechat-ui":
                continue
            data = candidate.read_bytes()
            if SECRET.search(data):
                raise AdapterError("delivery_secret_pattern_detected")
            files.append((relative.as_posix(), candidate, hashlib.sha256(data).hexdigest()))
    return files


def inspect_video(path):
    if path is None:
        return {"status": "not_provided"}
    if (
        path.suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}
        or not path.is_file()
        or path.stat().st_size < 1024
    ):
        raise AdapterError("delivery_video_missing_or_empty")
    probe = shutil.which("ffprobe")
    if not probe:
        return {"status": "probe_unavailable", "bytes": path.stat().st_size}
    try:
        result = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                str(path.resolve()),
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        if duration <= 0 or not any(s["codec_type"] == "video" for s in data["streams"]):
            raise ValueError()
        return {
            "status": "media_probe_passed",
            "duration_seconds": duration,
            "bytes": path.stat().st_size,
        }
    except (subprocess.SubprocessError, ValueError, KeyError, OSError):
        raise AdapterError("delivery_video_invalid") from None


def verify(root, video=None):
    files = source_files(root)
    present = {name for name, _, _ in files}
    missing = [name for name in REQUIRED if name not in present]
    assets = any(
        name.startswith("src/wechat_reply_agent/web/assets/") and name.endswith(".js")
        for name in present
    )
    if not assets:
        missing.append("bundled_workbench_javascript")
    if "pyproject.toml" in present:
        try:
            project = tomllib.loads((root / "pyproject.toml").read_text())
            source = project["tool"]["uv"]["sources"]["wechatauto-replica"]["path"]
            if source != "third_party/wechatauto_replica":
                missing.append("relative_windows_dependency")
        except (ValueError, KeyError, TypeError):
            missing.append("relative_windows_dependency")
    if "src/wechat_reply_agent/web/index.html" in present:
        html = (root / "src/wechat_reply_agent/web/index.html").read_text()
        references = re.findall(r'(?:src|href)="(/assets/[^"?#]+)"', html)
        if not references or any(
            "src/wechat_reply_agent/web" + ref not in present for ref in references
        ):
            missing.append("bundled_workbench_asset_references")
    summary = {}
    if "docs/acceptance-summary.json" in present:
        summary = json.loads((root / "docs/acceptance-summary.json").read_text())
    human = summary.get("human_gates", {})
    automatic = summary.get("offline", {})
    pending_automatic = [
        key
        for key in (
            "python_tests",
            "ruff",
            "frontend_build",
            "service_replay",
            "source_archive_scan",
        )
        if automatic.get(key) != "passed"
    ]
    pending = [
        key
        for key in (
            "windows_native_regression",
            "mac_strict_g1_g2",
            "windows_phase7_workbench",
            "mac_phase7_workbench",
            "windows_clean_install",
            "mac_clean_install",
            "video_review",
            "privacy_review",
        )
        if human.get(key) != "passed"
    ]
    media = inspect_video(video)
    if media["status"] != "media_probe_passed":
        pending.append("playable_real_video")
    return {
        "phase": 9,
        "plan_version": "v5",
        "created": datetime.now(UTC).isoformat(),
        "source_status": "passed" if not missing else "failed",
        "missing": missing,
        "file_count": len(files),
        "secret_pattern_scan": "passed",
        "video": media,
        "pending_human_gates": pending,
        "pending_automatic_checks": pending_automatic,
        "delivery_status": "ready"
        if not missing and not pending and not pending_automatic
        else "pending_acceptance",
        "note": "Known secret patterns scanned; user privacy/video review remains required.",
    }


def package(root, output, video=None, draft=False):
    report = verify(root, video)
    if report["source_status"] != "passed":
        raise AdapterError("delivery_source_incomplete")
    if not draft and report["delivery_status"] != "ready":
        raise AdapterError("delivery_human_acceptance_pending_use_draft")
    if output.exists():
        raise AdapterError("delivery_output_exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = source_files(root)
    manifest = report | {
        "kind": "source_draft" if draft else "final_submission",
        "files": {name: digest for name, _, digest in files},
    }
    prefix = "wechat-reply-agent/"
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path, _ in files:
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
                    raise AdapterError("delivery_source_changed")
                info = zipfile.ZipInfo.from_file(path, prefix + name)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
            if video:
                archive.write(video, prefix + "demo/real-demo" + video.suffix.lower())
                with video.open("rb") as stream:
                    manifest["files"]["demo/real-demo" + video.suffix.lower()] = (
                        hashlib.file_digest(stream, "sha256").hexdigest()
                    )
            archive.writestr(
                prefix + "delivery-manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return report | {"kind": manifest["kind"], "archive_sha256": digest}
