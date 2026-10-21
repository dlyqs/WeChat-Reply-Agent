"""Initialize a private G1 evidence ledger. Never probes the desktop or overwrites results."""

import json
import platform
import subprocess
from pathlib import Path

from wechat_reply_agent.cli import write_private


def main():
    path = Path(".local/acceptance/phase-1/report.json")
    if path.exists():
        print("Existing report preserved; update manual evidence in place.")
        return
    cases = [
        ("P01-01", "assistant", "Portable import/config/offline tests; doctor never initializes"),
        (
            "P01-02",
            "assistant+user",
            "Windows version, process account, private cache and initialization are verified",
        ),
        (
            "P01-03",
            "assistant+user",
            "One friend, five texts including duplicates and self direction",
        ),
        (
            "P01-04",
            "assistant+user",
            "Dry-run, one fixed reply, recipient confirmation and refusals",
        ),
        (
            "P01-05",
            "assistant",
            "Inclusive cross-shard cursor, old readback, stale/corrupt snapshots",
        ),
    ]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    payload = {
        "plan_version": "v4",
        "foundation": "replica",
        "phase": 1,
        "commit": commit,
        "mode": "offline+manual_pending",
        "environment": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "wechat_version": "not_tested",
            "distribution": "not_tested",
            "language": "not_tested",
            "second_version": "not_tested",
        },
        "cases": [
            {
                "id": case,
                "executor": who,
                "expected": expected,
                "actual": "not run",
                "status": "not_tested",
                "evidence_ref": None,
            }
            for case, who, expected in cases
        ],
        "failures": [],
        "g1": "not_tested",
        "note": "User records actual desktop/recipient results; initializer never asserts passed.",
    }
    write_private(path, payload)
    print(json.dumps({"report": str(path), "g1": "not_tested"}))


if __name__ == "__main__":
    main()
