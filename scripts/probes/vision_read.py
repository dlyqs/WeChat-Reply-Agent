"""Wait for the user-selected test chat, then run local read-only OCR once."""

import argparse
import json
import time
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.profile import load_profile
from wechat_reply_agent.adapters.wechat.vision_diagnostic import capture_target
from wechat_reply_agent.cli import probe_lock, write_private
from wechat_reply_agent.config import Settings


def main():
    import AppKit
    from Foundation import NSDate, NSRunLoop

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contact", required=True)
    parser.add_argument("--wait-seconds", type=int, default=300, choices=range(1, 301))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    profile = load_profile(settings.wechat_profile)
    if args.contact not in settings.wechat_allowlist:
        raise AdapterError("contact_not_allowlisted")
    contacts = [c for c in profile.contacts if c.alias == args.contact and c.single_chat_confirmed]
    if len(contacts) != 1 or not profile.account_confirmed:
        raise AdapterError("contact_binding_unconfirmed")
    status = args.output.with_name("vision-wait.json")
    write_private(status, {"status": "waiting_for_wechat_foreground", "sending": False})
    deadline = time.monotonic() + args.wait_seconds
    while time.monotonic() < deadline:
        front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if front and front.bundleIdentifier() == "com.tencent.xinWeChat":
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.3))
            try:
                with probe_lock(settings.data_dir):
                    result = capture_target(contacts[0].title)
                    write_private(args.output, result)
                write_private(
                    status,
                    {
                        "status": "completed",
                        "sending": False,
                        "observations": len(result["observations"]),
                    },
                )
                print(
                    json.dumps(
                        {
                            "status": "completed",
                            "title_matched": True,
                            "observations": len(result["observations"]),
                        }
                    )
                )
                return 0
            except Exception as exc:
                code = str(exc) if isinstance(exc, AdapterError) else "vision_diagnostic_failed"
                write_private(status, {"status": "rejected", "code": code, "sending": False})
                print(json.dumps({"status": "rejected", "code": code}))
                return 2
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.5))
    write_private(status, {"status": "timed_out", "sending": False})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
