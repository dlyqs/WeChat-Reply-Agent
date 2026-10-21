"""One application lifecycle; restarting always establishes a fresh baseline."""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.llm.client import CompatibleModel
from wechat_reply_agent.runtime.prototype import Prototype
from wechat_reply_agent.runtime.worker import execute
from wechat_reply_agent.storage.database import Ledger
from wechat_reply_agent.storage.migrations import bind_identity
from wechat_reply_agent.storage.repositories import Repository
from wechat_reply_agent.storage.retention import prune_replica_cache


class RuntimeService:
    def __init__(self, store, adapter_factory=None, model_factory=CompatibleModel):
        from wechat_reply_agent.cli import create_adapter

        self.store = store
        self.adapter_factory = adapter_factory or create_adapter
        self.model_factory = model_factory
        self.path = store.settings.data_dir / "prototype.sqlite3"
        self.repo = Repository(self.path)
        self.repo.recover()
        self.file_identity = self._identity()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wechat-gui")
        self.guard = threading.RLock()
        self.cancel = threading.Event()
        self.runtime = None
        self.future = None
        self.state, self.reason, self.connected = "stopped", "start_required", False
        self.generation = self.repo.runtime_state(self.state, self.reason)
        self.closed = False
        self.native_files = {}

    @property
    def settings(self):
        return self.store.settings

    def _identity(self):
        try:
            stat = self.path.stat()
            return stat.st_dev, stat.st_ino
        except OSError:
            raise AdapterError("application_database_replaced") from None

    def check_database(self):
        if self._identity() != self.file_identity:
            raise AdapterError("application_database_replaced")
        for path, identity in self.native_files.items():
            try:
                stat = path.stat()
            except OSError:
                raise AdapterError("native_database_replaced") from None
            if (stat.st_dev, stat.st_ino) != identity:
                raise AdapterError("native_database_replaced")

    def _same_database(self):
        try:
            return self._identity() == self.file_identity
        except AdapterError:
            return False

    def snapshot(self):
        with self.guard:
            steps = getattr(self.runtime, "connection_steps", None) or {}
            public_steps = {
                k: v
                for k, v in steps.items()
                if k in {"keys", "account", "private_cache", "gui", "uia"}
                and v in {"ready", "verified", "initialized", "available", "unavailable"}
            }
            return {
                "state": self.state,
                "reason": self.reason,
                "connected": self.connected,
                "mode": self.settings.send_mode,
                "generation": self.generation,
                "sent_this_run": self.runtime.sent_count if self.runtime else 0,
                "max_replies": 3,
                "initialization": public_steps,
            }

    def _gates(self):
        try:
            for phase in (1, 2):
                report = json.loads(
                    (self.settings.data_dir / f"acceptance/phase-{phase}/report.json").read_text(
                        encoding="utf-8"
                    )
                )
                if (
                    report.get(f"g{phase}") != "passed"
                    or report.get("foundation") != "replica"
                    or report.get("plan_version") != "v4"
                ):
                    raise ValueError
        except (OSError, ValueError):
            raise AdapterError("g1_g2_reports_required") from None

    def start(self, resume=False):
        with self.guard:
            if self.state not in (("paused",) if resume else ("stopped", "degraded")):
                raise AdapterError("runtime_transition_invalid")
            if self.future and not self.future.done():
                raise AdapterError("worker_still_stopping")
            if not self.settings.wechat_allowlist:
                raise AdapterError("nonempty_allowlist_required")
            if not self.settings.llm_api_key.get_secret_value():
                raise AdapterError("model_key_missing")
            if self.settings.poll_interval_seconds < 10:
                raise AdapterError("poll_minimum_10_seconds")
            self.check_database()
            self._gates()
            self.state, self.reason = "starting", "connect_requested"
            self.runtime = None
            self.generation += 1
            self.repo.runtime_state(self.state, self.reason)
            self.cancel.clear()
            self.future = self.executor.submit(self._work)
        return self.snapshot()

    def _work(self):
        ledger = None
        try:
            self.check_database()
            prune_replica_cache(self.settings.data_dir, self.settings.retention_days)
            adapter = self.adapter_factory(self.settings, profile_required=True)
            if hasattr(adapter, "validate_profile"):
                adapter.validate_profile()
            for alias in self.settings.wechat_allowlist:
                adapter.resolve_conversation(alias)
            profile = adapter.profile
            root = profile.db_root / profile.account / "db_storage"
            files = {}
            for path in sorted(root.rglob("*.db")):
                stat = path.stat()
                files[path] = (stat.st_dev, stat.st_ino)
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "account_ref": profile.account_ref,
                        "generation": profile.account_generation,
                        "account": profile.account,
                        "self": profile.self_username,
                        "root": str(profile.db_root.resolve()),
                        "databases": [
                            (str(p.relative_to(root)), identity) for p, identity in files.items()
                        ],
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            ledger = Ledger(self.path)
            bind_identity(ledger.db, fingerprint, profile.account_ref, profile.account_generation)
            self.native_files = files
            scope = ":".join(
                [profile.account_generation, profile.account_ref, self.settings.send_mode]
            )
            with ledger.db:
                for contact in profile.contacts:
                    ledger.db.execute(
                        "INSERT OR REPLACE INTO contacts VALUES(?,?,?)",
                        (scope, contact.alias, contact.username),
                    )
            runtime = Prototype(self.settings, adapter, self.model_factory(self.settings), ledger)
            runtime.before_send = self.check_database
            with self.guard:
                self.runtime = runtime
                if self.cancel.is_set():
                    return
            execute(self, runtime)
        except Exception as exc:
            # Exceptions may include private paths or native data; publish only an allowlisted code.
            with self.guard:
                if not self.cancel.is_set():
                    known = {
                        "account_or_database_binding_changed",
                        "application_database_replaced",
                        "native_database_replaced",
                        "unresolved_outbox_stop_required",
                        "queue_full_degraded",
                        "replica_profile_missing_or_invalid",
                        "account_binding_required",
                        "database_root_mismatch",
                        "database_root_missing",
                    }
                    reason = (
                        str(exc)
                        if isinstance(exc, AdapterError) and str(exc) in known
                        else "worker_failed"
                    )
                    self.state, self.reason, self.connected = "degraded", reason, False
        finally:
            if ledger:
                ledger.close()
            with self.guard:
                self.connected = False
                if self._same_database():
                    self.generation = self.repo.runtime_state(self.state, self.reason)

    def halt(self, pause=False):
        # Send gate is acquired before guard to avoid inversion with worker snapshot updates.
        with self.guard:
            if pause and self.state not in ("running", "starting"):
                raise AdapterError("runtime_transition_invalid")
        runtime = self.runtime
        if runtime:
            runtime.stop("paused" if pause else "stopped")
        with self.guard:
            self.cancel.set()
            self.generation += 1
            self.state, self.reason = "stopping", "pause_requested" if pause else "stop_requested"
            future = self.future
        if future:
            # Bounded model timeout; finish/join before reporting paused/stopped.
            future.result()
        if self._same_database():
            self.repo.recover()
        with self.guard:
            self.state = "paused" if pause else "stopped"
            self.reason, self.connected = self.state, False
            if self._same_database():
                self.generation = self.repo.runtime_state(self.state, self.reason)
        return self.snapshot()

    def diagnostic(self):
        with self.guard:
            if self.state not in ("stopped", "paused", "degraded"):
                raise AdapterError("stop_before_diagnostic")

        def read_only():
            adapter = self.adapter_factory(self.settings, profile_required=False)
            health = adapter.health()
            # Do not publish raw upstream environment objects or local account paths.
            return {
                "healthy": health.healthy,
                "reason": health.reason,
                "capabilities": health.capabilities.model_dump(mode="json"),
                "connected": False,
                "initialization": "explicit_start_required",
            }

        return self.executor.submit(read_only).result()

    def close(self):
        if not self.closed:
            try:
                self.halt()
            finally:
                self.executor.shutdown(wait=True, cancel_futures=True)
                self.closed = True
