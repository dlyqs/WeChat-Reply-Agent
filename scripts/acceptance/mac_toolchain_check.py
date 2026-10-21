"""Exercise LLDB capture with an owned synthetic process and encrypted toy DB only."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from wechat_reply_agent.adapters.wechat.mac_bridge import TOOLKIT, toolkit_module
from wechat_reply_agent.cli import write_private
from wechat_reply_agent.privacy import private_directory


def check(directory):
    private_directory(directory)
    root = directory / "fixture"
    private_directory(root)
    database = root / "fixture.db"
    if database.exists():
        raise RuntimeError("toolchain_check_requires_fresh_directory")
    sql = toolkit_module("sqlcipher_probe")
    secret = os.urandom(32)
    with sql.DB(database, secret.hex(), fixture_write=True) as db:
        db.query("CREATE TABLE fixture(id INTEGER); INSERT INTO fixture VALUES(1);")
    database.chmod(0o600)
    salt = bytes(v ^ 0x3A for v in database.read_bytes()[:16])
    source = directory / "fixture.c"
    source.write_text(
        "#include <CommonCrypto/CommonKeyDerivation.h>\n"
        "int main(void) {\n"
        "unsigned char password[32] = {" + ",".join(map(str, secret)) + "};\n"
        "unsigned char salt[16] = {" + ",".join(map(str, salt)) + "};\n"
        "unsigned char output[32];\n"
        "return CCKeyDerivationPBKDF(kCCPBKDF2, (const char *)password, 32, "
        "salt, 16, kCCPRFHmacAlgSHA512, 2, output, 32);\n}\n"
    )
    source.chmod(0o600)
    binary = directory / "fixture-process"
    subprocess.run(
        ["/usr/bin/xcrun", "clang", "-g", "-O0", str(source), "-o", str(binary)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = subprocess.check_output(["/usr/bin/lldb", "-P"], text=True).strip()
    env.pop("PYTHONHOME", None)
    started = time.monotonic()
    keys = directory / "fixture-keys.json"
    result = subprocess.run(
        [
            "/usr/bin/python3",
            str(TOOLKIT / "capture_keys.py"),
            "--exe",
            str(binary.resolve()),
            "--db-root",
            str(root.resolve()),
            "--out",
            str(keys.resolve()),
            "--timeout",
            "15",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    log = directory / "capture.jsonl"
    log.write_text(result.stdout + result.stderr)
    log.chmod(0o600)
    valid = False
    if keys.is_file():
        key = sql.load_key(keys, database)
        valid = key == secret.hex() and sql.verify(database, keys)["verified"]
    report = {
        "mode": "synthetic_owned_process_only",
        "wechat_accessed": False,
        "lldb": subprocess.check_output(["/usr/bin/lldb", "--version"], text=True).strip(),
        "sdk": subprocess.check_output(
            ["/usr/bin/xcrun", "--sdk", "macosx", "--show-sdk-version"], text=True
        ).strip(),
        "exit_code": result.returncode,
        "captured_key_verified": valid,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "passed": result.returncode == 0 and valid,
    }
    write_private(directory / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.directory)
    print(json.dumps(report))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
