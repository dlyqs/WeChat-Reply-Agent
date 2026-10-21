"""Explicit Windows probes and bounded Agent prototype; never opens a browser."""

import argparse
import json
import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings.exceptions import SettingsError

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.profile import load_profile
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import SendIntent
from wechat_reply_agent.observability import emit
from wechat_reply_agent.privacy import private_directory


def write_private(path: Path, payload: dict):
    private_directory(path.parent)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".report-")
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def probe_lock(data_dir: Path):
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(data_dir / "probe.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise AdapterError("another_probe_running") from exc
        yield
    finally:
        os.close(fd)


def create_adapter(settings: Settings, *, profile_required: bool):
    if settings.wechat_adapter == "mac_db":
        from wechat_reply_agent.adapters.wechat.mac_db import MacAdapter
        from wechat_reply_agent.adapters.wechat.mac_profile import load_mac_profile

        try:
            profile = load_mac_profile(settings.wechat_profile)
        except AdapterError:
            if profile_required:
                raise
            profile = None
        return MacAdapter(settings, profile)
    if settings.wechat_adapter == "replica":
        from wechat_reply_agent.adapters.wechat.replica import ReplicaAdapter
        from wechat_reply_agent.adapters.wechat.replica_profile import load_replica_profile

        try:
            profile = load_replica_profile(settings.wechat_profile)
        except AdapterError:
            if profile_required:
                raise
            profile = None
        return ReplicaAdapter(settings, profile)
    if settings.wechat_adapter != "mac_ax":
        # Fake is injection-only. A CLI invocation must never pretend fake data is WeChat.
        raise AdapterError("fake_adapter_is_offline_test_only")
    try:
        profile = load_profile(settings.wechat_profile)
    except AdapterError:
        if profile_required:
            raise
        profile = None
    from wechat_reply_agent.adapters.wechat.mac_ax import MacAXAdapter

    return MacAXAdapter(settings, profile)


def parser():
    root = argparse.ArgumentParser(prog="wechat-agent", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    serve = commands.add_parser(
        "serve", help="Loopback API and bundled workbench; initially stopped"
    )
    serve.add_argument("--host", choices=("127.0.0.1", "localhost", "::1"))
    serve.add_argument("--port", type=int)
    doctor = commands.add_parser("doctor", help="Read-only permission/environment diagnostic")
    doctor.add_argument("--output", type=Path, required=True)
    connect = commands.add_parser(
        "connect", help="Explicit key/cache/calibration/UIA initialization"
    )
    connect.add_argument("--output", type=Path, required=True)
    bootstrap = commands.add_parser(
        "mac-bootstrap", help="Explicit temporary-copy key capture; quit WeChat normally first"
    )
    bootstrap.add_argument("--db-root", type=Path, required=True)
    bootstrap.add_argument("--state-dir", type=Path, required=True)
    bootstrap.add_argument("--timeout", type=int, default=180)
    bootstrap.add_argument(
        "--resume-prepared",
        action="store_true",
        help="Resume the same pinned copy after granting its data access permission",
    )
    bootstrap.add_argument(
        "--prepared-app", type=Path, help="Exact authorized copy path; requires --resume-prepared"
    )
    bootstrap.add_argument("--output", type=Path, required=True)
    reset = commands.add_parser(
        "mac-security-reset", help="Record manual login confirmation; never log in or send"
    )
    reset.add_argument("--confirm-manual-login", action="store_true")
    reset.add_argument("--output", type=Path, required=True)
    probe = commands.add_parser("probe", help="User-operated current test single-chat probes")
    actions = probe.add_subparsers(dest="action", required=True)
    read = actions.add_parser("read", help="Read visible messages; never scroll or select a chat")
    read.add_argument("--contact", required=True)
    read.add_argument("--limit", type=int, choices=range(1, 51), default=5, metavar="1..50")
    read.add_argument("--output", type=Path, required=True)
    send = actions.add_parser("send", help="Explicit fixed reply; Return is not delivery proof")
    send.add_argument("--contact", required=True)
    send.add_argument("--text", required=True)
    send.add_argument("--confirm-send", action="store_true")
    send.add_argument("--output", type=Path)
    resolve = commands.add_parser("resolve", help="Record human verification of an uncertain probe")
    resolve.add_argument("--outbox-id", required=True)
    resolve.add_argument("--resolution", choices=("sent", "discarded"), required=True)
    resolve.add_argument("--ledger", action="store_true", help="Resolve a prototype SQLite outbox")
    prototype = commands.add_parser("prototype", help="Bounded minimal Agent; new messages only")
    prototype.add_argument("--mode", choices=("dry-run", "live"), default="dry-run")
    prototype.add_argument("--duration", type=int, choices=range(1, 1801), default=600)
    prototype.add_argument("--max-replies", type=int, choices=range(1, 4), default=3)
    prototype.add_argument(
        "--allow-degraded-mac-ui",
        action="store_true",
        help="Explicit flow-only Mac run without visual draft checks; does not pass G1/G2",
    )
    prototype.add_argument(
        "--output", type=Path, default=Path(".local/acceptance/phase-2/prototype.json")
    )
    return root


def execute(args, settings: Settings, adapter):
    if args.command == "doctor":
        health = adapter.health()
        emit(
            "adapter.health",
            outcome="available" if health.healthy else "unavailable",
            reason=health.reason,
        )
        report = {
            "plan_version": "v5" if settings.wechat_adapter == "mac_db" else "v4",
            "foundation": settings.wechat_adapter,
            "platform": "macOS" if settings.wechat_adapter == "mac_db" else "Windows",
            "phase": 5 if settings.wechat_adapter == "mac_db" else 1,
            "mode": "diagnostic",
            "health": health.model_dump(mode="json"),
            "g1": "not_tested",
            "note": "No send, app activation or permission changes",
        }
        write_private(args.output, report)
        return 0 if health.healthy else 2
    with probe_lock(settings.data_dir):
        if args.command == "mac-security-reset":
            from wechat_reply_agent.adapters.wechat.mac_security import clear_security_stop

            if settings.wechat_adapter != "mac_db":
                raise AdapterError("mac_db_adapter_required")
            result = clear_security_stop(settings, confirmed=args.confirm_manual_login)
            write_private(args.output, result)
            return 0
        if args.command == "mac-bootstrap":
            from wechat_reply_agent.adapters.wechat.mac_bootstrap import bootstrap
            from wechat_reply_agent.adapters.wechat.mac_security import require_security_clear

            require_security_clear(settings)

            if not args.state_dir.resolve().is_relative_to(settings.data_dir.resolve()):
                raise AdapterError("bootstrap_must_use_private_data_dir")
            result = bootstrap(
                args.db_root,
                args.state_dir,
                timeout=args.timeout,
                resume_prepared=args.resume_prepared,
                prepared_app=args.prepared_app,
            )
            write_private(args.output, result)
            return 0
        if args.command == "prototype":
            import asyncio

            from wechat_reply_agent.llm.client import CompatibleModel
            from wechat_reply_agent.runtime.prototype import Prototype
            from wechat_reply_agent.storage.prototype import Ledger

            if (
                getattr(args, "allow_degraded_mac_ui", False)
                and settings.wechat_adapter != "mac_db"
            ):
                raise AdapterError("degraded_ui_flag_is_mac_only")
            if settings.wechat_adapter == "mac_db":
                from wechat_reply_agent.adapters.wechat.mac_acceptance import (
                    require_degraded_prototype,
                    require_gate,
                )

                if getattr(args, "allow_degraded_mac_ui", False):
                    require_degraded_prototype(settings, adapter.profile)
                else:
                    require_gate(settings, adapter.profile)
            elif settings.wechat_adapter == "replica":
                try:
                    gate = json.loads(
                        (settings.data_dir / "acceptance/phase-1/report.json").read_text(
                            encoding="utf-8"
                        )
                    )
                except (ValueError, OSError):
                    raise AdapterError("g1_report_required") from None
                if (
                    gate.get("g1") != "passed"
                    or gate.get("plan_version") != "v4"
                    or gate.get("foundation") != "replica"
                ):
                    raise AdapterError("replica_g1_required")
            else:
                raise AdapterError("native_adapter_required")
            if not settings.llm_api_key.get_secret_value():
                raise AdapterError("real_model_required")
            if settings.poll_interval_seconds < 10:
                raise AdapterError("prototype_poll_minimum_10_seconds")
            settings.send_mode = args.mode
            ledger = Ledger(settings.data_dir / "prototype.sqlite3")
            try:
                runtime = Prototype(settings, adapter, CompatibleModel(settings), ledger)
                return asyncio.run(runtime.run(args.duration, args.max_replies, args.output))
            finally:
                ledger.close()
        if args.command == "resolve":
            from uuid import UUID

            try:
                outbox_id = str(UUID(args.outbox_id))
                if args.ledger:
                    from wechat_reply_agent.storage.prototype import Ledger

                    ledger_path = settings.data_dir / "prototype.sqlite3"
                    if not ledger_path.exists():
                        raise AdapterError("prototype_ledger_missing")
                    ledger = Ledger(ledger_path)
                    try:
                        if settings.wechat_adapter == "mac_db":
                            candidate = ledger.db.execute(
                                "SELECT state,resolution FROM outbox WHERE id=?", (outbox_id,)
                            ).fetchone()
                            if (
                                not candidate
                                or candidate[0] not in ("unknown", "paused")
                                or candidate[1] is not None
                            ):
                                raise AdapterError("unknown_outbox_missing")
                            from wechat_reply_agent.adapters.wechat.mac_db import (
                                resolve_native_operation,
                            )

                            resolve_native_operation(settings, outbox_id, args.resolution)
                        ledger.resolve(outbox_id, args.resolution)
                    finally:
                        ledger.close()
                    return 0
                receipt = settings.data_dir / "probe-sends" / f"{outbox_id}.json"
                record = json.loads(receipt.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise AdapterError("probe_receipt_missing_or_invalid") from None
            if record.get("outcome") != "unknown":
                raise AdapterError("probe_not_uncertain")
            if settings.wechat_adapter == "mac_db":
                from wechat_reply_agent.adapters.wechat.mac_db import resolve_native_operation

                resolve_native_operation(settings, outbox_id, args.resolution)
            record["resolution"] = args.resolution
            write_private(receipt, record)
            return 0
        if args.command == "connect":
            result = adapter.connect()
            write_private(
                args.output,
                {
                    "phase": 5 if settings.wechat_adapter == "mac_db" else 1,
                    "plan_version": "v5" if settings.wechat_adapter == "mac_db" else "v4",
                    "foundation": settings.wechat_adapter,
                    "platform": "macOS" if settings.wechat_adapter == "mac_db" else "Windows",
                    "mode": "connect",
                    "steps": result,
                    "g1": "not_tested",
                },
            )
            emit("adapter.connect", outcome="initialized")
            return 0
        ref = adapter.resolve_conversation(args.contact)
        if args.action == "send":
            if not args.confirm_send:
                raise AdapterError("explicit_confirm_send_required")
            for old in (settings.data_dir / "probe-sends").glob("*.json"):
                try:
                    record = json.loads(old.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raise AdapterError("probe_receipt_invalid_stop_required") from None
                if record.get("outcome") == "unknown" and not record.get("resolution"):
                    raise AdapterError("unresolved_probe_stop_required")
        if settings.wechat_adapter in ("replica", "mac_db") and not (
            args.action == "send" and settings.send_mode == "dry-run"
        ):
            adapter.connect()
        if args.action == "read":
            if settings.wechat_adapter == "mac_db":
                events, cursor = adapter.read_recent(args.contact, args.limit), None
            else:
                events, cursor = adapter.poll_events()
            report = {
                "plan_version": "v5" if settings.wechat_adapter == "mac_db" else "v4",
                "foundation": settings.wechat_adapter,
                "platform": "macOS" if settings.wechat_adapter == "mac_db" else "Windows",
                "phase": 5 if settings.wechat_adapter == "mac_db" else 1,
                "mode": "probe_read",
                "g1": "not_tested",
                "conversation": ref.model_dump(),
                "cursor": cursor,
                "events": [
                    e.model_dump(mode="json")
                    for e in events
                    if e.conversation_id == ref.conversation_id
                ][-args.limit :],
                "note": "Native database identities; private evidence only",
            }
            write_private(args.output, report)
            emit("adapter.read", outcome="snapshot")
            return 0
        if not args.confirm_send:
            raise AdapterError("explicit_confirm_send_required")
        intent = SendIntent(conversation=ref, reply_text=args.text, mode=settings.send_mode)
        # Persist before the key boundary. A crash leaves unknown, never an automatic retry.
        receipt = settings.data_dir / "probe-sends" / f"{intent.outbox_id}.json"
        report = {
            "plan_version": "v5" if settings.wechat_adapter == "mac_db" else "v4",
            "foundation": settings.wechat_adapter,
            "platform": "macOS" if settings.wechat_adapter == "mac_db" else "Windows",
            "phase": 5 if settings.wechat_adapter == "mac_db" else 1,
            "mode": intent.mode,
            "outbox_id": intent.outbox_id,
            "g1": "not_tested",
            "outcome": "unknown",
            "basis": "probe_started",
            "note": "Check recipient manually. No automatic retries or delivery claim.",
        }
        if settings.wechat_adapter == "mac_db":
            from wechat_reply_agent.adapters.wechat.mac_acceptance import context

            report.update(context(adapter.profile))
        write_private(receipt, report)
        result = adapter.send_text(intent)
        report.update(result.model_dump())
        write_private(receipt, report)
        if args.output:
            write_private(args.output, report)
        emit("send.result", outcome=result.outcome, reason=result.basis)
        # No raw text/contact/profile contents in terminal logs.
        print(
            json.dumps(
                {
                    "outbox_id": intent.outbox_id,
                    "mode": intent.mode,
                    "outcome": result.outcome,
                    "receipt": str(receipt),
                }
            )
        )
        return 3 if result.outcome == "unknown" else (0 if result.error is None else 2)


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = None
    try:
        settings = Settings()
        if args.command == "serve":
            if settings.wechat_adapter == "mac_db":
                raise AdapterError("mac_service_requires_phase6")
            import uvicorn

            from wechat_reply_agent.api.app import create_app
            from wechat_reply_agent.settings_store import SettingsStore

            # Each server launch requires explicit live selection in the workbench.
            overrides = {"send_mode": "dry-run"}
            if args.host:
                overrides["app_host"] = args.host
            if args.port is not None:
                overrides["app_port"] = args.port
            settings = Settings.model_validate(settings.model_dump() | overrides)
            with probe_lock(settings.data_dir):
                app = create_app(SettingsStore(settings=settings, session_fields=overrides))
                uvicorn.run(
                    app,
                    host=settings.app_host,
                    port=settings.app_port,
                    access_log=False,
                    log_level="warning",
                )
            return 0
        adapter = create_adapter(
            settings,
            profile_required=args.command
            not in ("doctor", "resolve", "mac-bootstrap", "mac-security-reset"),
        )
        return execute(args, settings, adapter)
    except (ValidationError, SettingsError):
        error = "configuration_invalid"
    except AdapterError as exc:
        error = str(exc)
    except Exception:
        error = "local_or_native_operation_failed"
    except KeyboardInterrupt:
        emit("operation.stop", outcome="cancelled")
        return 130
    output = getattr(args, "output", None)
    if output:
        try:
            write_private(
                output,
                {
                    "phase": 5
                    if settings and settings.wechat_adapter == "mac_db"
                    else 2
                    if args.command == "prototype"
                    else 1,
                    "plan_version": "v5"
                    if settings and settings.wechat_adapter == "mac_db"
                    else "v4",
                    "g2" if args.command == "prototype" else "g1": "not_tested",
                    "status": "failed",
                    "code": error,
                },
            )
        except OSError:
            pass
    emit("probe.error", outcome="rejected", reason=error)
    print(json.dumps({"code": error, "message": "See README G1 troubleshooting"}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
