"""One application lifecycle; restarting always establishes a fresh baseline."""

import threading
from concurrent.futures import ThreadPoolExecutor

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.llm.client import CompatibleModel
from wechat_reply_agent.runtime.prototype import Prototype
from wechat_reply_agent.runtime.worker import execute
from wechat_reply_agent.storage.database import Ledger
from wechat_reply_agent.storage.migrations import bind_identity
from wechat_reply_agent.storage.repositories import Repository


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
        self.binding = None
        self.adapter_info = {}

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
        if self.binding:
            self.binding.check_sources()

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
                "platform": self.adapter_info.get(
                    "platform", "macOS" if self.settings.wechat_adapter == "mac_db" else "Windows"
                ),
                "foundation": self.settings.wechat_adapter,
                "capabilities": self.adapter_info,
            }

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
            self.state, self.reason = "starting", "connect_requested"
            self.runtime = None
            self.generation += 1
            self.repo.runtime_state(self.state, self.reason)
            self.cancel.clear()
            self.future = self.executor.submit(self._work)
        return self.snapshot()

    def _work(self):
        ledger = adapter = None
        try:
            self.check_database()
            adapter = self.adapter_factory(self.settings, profile_required=True)
            for alias in self.settings.wechat_allowlist:
                adapter.resolve_conversation(alias)
            binding = adapter.runtime_binding()
            adapter.require_runtime_acceptance(binding)
            info = adapter.runtime_info()
            if self.settings.max_reply_characters > info["max_text_characters"]:
                raise AdapterError("reply_limit_exceeds_adapter_capability")
            adapter.prune_cache()
            ledger = Ledger(self.path)
            bind_identity(
                ledger.db, binding.fingerprint, binding.account_ref, binding.account_generation
            )
            with ledger.db:
                for key, value in {
                    "platform": info["platform"],
                    "foundation": info["foundation"],
                }.items():
                    previous = ledger.db.execute(
                        "SELECT value FROM metadata WHERE key=?", (key,)
                    ).fetchone()
                    if previous and previous[0] != value:
                        raise AdapterError("account_or_database_binding_changed")
                    ledger.db.execute("INSERT OR IGNORE INTO metadata VALUES(?,?)", (key, value))
            self.binding = binding
            self.adapter_info = info
            scope = ":".join(
                [binding.account_generation, binding.account_ref, self.settings.send_mode]
            )
            with ledger.db:
                for contact in binding.contacts:
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
                        "account_binding_required",
                        "database_root_mismatch",
                        "database_root_missing",
                        "reply_limit_exceeds_adapter_capability",
                    }
                    reason = (
                        str(exc)
                        if isinstance(exc, AdapterError) and str(exc) in known
                        else adapter.public_error(exc)
                        if adapter
                        else "worker_failed"
                    )
                    self.state, self.reason, self.connected = "degraded", reason, False
        finally:
            try:
                if adapter:
                    adapter.close()
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
            try:
                health = adapter.health()
                self.adapter_info = adapter.runtime_info()
                return {
                    "healthy": health.healthy,
                    "reason": health.reason,
                    "platform": self.adapter_info["platform"],
                    "foundation": self.settings.wechat_adapter,
                    "capabilities": health.capabilities.model_dump(mode="json"),
                    "permissions": {
                        k: v
                        for k, v in health.environment.items()
                        if k
                        in {
                            "screen_locked",
                            "screen_recording",
                            "accessibility",
                            "account_security_stop",
                        }
                    },
                    "connected": False,
                    "initialization": "explicit_start_required",
                }
            finally:
                adapter.close()

        return self.executor.submit(read_only).result()

    def resolve(self, outbox_id, resolution):
        if self._identity() != self.file_identity:
            raise AdapterError("application_database_replaced")
        if resolution not in ("sent", "discarded"):
            raise AdapterError("resolution_invalid")

        def record_only():
            ledger = Ledger(self.path)
            adapter = None
            try:
                row = ledger.db.execute(
                    "SELECT state,resolution FROM outbox WHERE id=?", (outbox_id,)
                ).fetchone()
                if not row or row[0] not in ("unknown", "paused") or row[1] is not None:
                    raise AdapterError("unknown_outbox_missing")
                adapter = self.adapter_factory(self.settings, profile_required=False)
                adapter.resolve_operation(outbox_id, resolution)
                ledger.resolve(outbox_id, resolution)
            finally:
                if adapter:
                    adapter.close()
                ledger.close()

        return self.executor.submit(record_only).result()

    def close(self):
        if not self.closed:
            try:
                self.halt()
            finally:
                self.executor.shutdown(wait=True, cancel_futures=True)
                self.closed = True
