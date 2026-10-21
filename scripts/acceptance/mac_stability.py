"""Bounded Mac read-only observation: no model, activation, clipboard, or sending."""

import argparse
import time

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.cli import create_adapter, probe_lock, write_private
from wechat_reply_agent.config import Settings


def observe(settings, duration, output):
    if settings.wechat_adapter != "mac_db":
        raise AdapterError("mac_db_adapter_required")
    adapter = create_adapter(settings, profile_required=True)
    started = time.monotonic()
    report = {
        "phase": 5,
        "plan_version": "v5",
        "platform": "macOS",
        "foundation": "mac_db",
        "mode": "read_only",
        "duration_seconds": duration,
        "checks": 0,
        "observed_events": 0,
        "model_calls": 0,
        "input_events": 0,
        "recipient_confirmed": False,
        "human_session_confirmation": "not_tested",
        "state": "starting",
    }
    try:
        with probe_lock(settings.data_dir):
            adapter.connect()
            _, cursor = adapter.poll_events(None)
            report["state"] = "observing"
            write_private(output, report)
            print('{"event":"readonly_observation_ready","input_events":0}', flush=True)
            while time.monotonic() - started < duration:
                events, cursor = adapter.poll_events(cursor)
                report["checks"] += 1
                report["observed_events"] += len(events)
                report["elapsed_seconds"] = round(time.monotonic() - started, 3)
                write_private(output, report)
                time.sleep(min(15, max(0, duration - (time.monotonic() - started))))
            adapter._ready()
            report["state"] = "observation_completed"
            report["reason"] = "no_native_session_error_observed"
    except AdapterError as exc:
        report.update(state="stopped", reason=str(exc))
    except KeyboardInterrupt:
        report.update(state="stopped", reason="operator_interrupted")
    except Exception:
        report.update(state="stopped", reason="readonly_observation_failed")
    finally:
        adapter.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_private(output, report)
    return 0 if report["state"] == "observation_completed" else 2


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, choices=range(60, 901), default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return observe(Settings(), args.duration, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
