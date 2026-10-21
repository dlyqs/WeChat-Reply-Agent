"""Bounded Phase 2 worker. Only this serialized path consumes durable outbox intents."""

import asyncio
import threading
import time

from langsmith import tracing_context

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.agent.graph import create_graph
from wechat_reply_agent.domain.messages import Direction, SendIntent, SendResult
from wechat_reply_agent.knowledge.store import KnowledgeStore
from wechat_reply_agent.memory.store import MemoryStore
from wechat_reply_agent.observability import emit


class Prototype:
    def __init__(self, settings, adapter, model, ledger):
        self.settings, self.adapter, self.ledger = settings, adapter, ledger
        self.binding = adapter.runtime_binding()
        self.scope = ":".join(
            [self.binding.account_generation, settings.wechat_account_ref, settings.send_mode]
        )
        self.graph = create_graph(
            settings, model, KnowledgeStore(ledger.path), MemoryStore(ledger.path), self.scope
        )
        self.generation = 0
        self.running = False
        self.reason = "stopped"
        self.sent_count = 0
        self.deadline = float("inf")
        self.poll_ms = 0
        self.started = 0
        self.send_gate = threading.RLock()
        self.before_send = lambda: None

    def eligible(self, event):
        p = self.binding
        sessions = {
            self.adapter.resolve_conversation(a).conversation_id
            for a in self.settings.wechat_allowlist
        }
        return (
            event.direction == Direction.INCOMING
            and event.type == "text"
            and bool(event.text)
            and event.confidence == 1
            and event.source_message_id == event.event_id
            and event.account_ref == p.account_ref
            and event.account_generation == p.account_generation
            and event.native_session in sessions
            and event.conversation_id in sessions
            and event.sender_username == event.native_session
        )

    def start(self):
        if not self.settings.wechat_allowlist:
            raise AdapterError("nonempty_allowlist_required")
        self.generation = self.ledger.begin_run()
        self.connection_steps = self.adapter.connect()
        with self.ledger.db:
            for contact in self.binding.contacts:
                self.ledger.db.execute(
                    "INSERT OR REPLACE INTO contacts VALUES(?,?,?)",
                    (self.scope, contact.alias, contact.username),
                )
        start = time.monotonic()
        events, cursor = self.adapter.poll_events(None)
        self.poll_ms = (time.monotonic() - start) * 1000
        self.ledger.ingest(
            self.scope, events, cursor, self.eligible, self.settings.queue_max_size, baseline=True
        )
        self.running, self.reason = True, "running"
        self.started = time.monotonic()
        emit("prototype.ready", outcome=self.settings.send_mode, reason="baseline_recorded")

    def stop(self, reason="stopped"):
        with self.send_gate:
            self.running = False
            self.generation += 1
            self.reason = reason

    async def tick(self):
        if not self.running:
            return
        start = time.monotonic()
        events, cursor = self.adapter.poll_events(self.ledger.cursor(self.scope))
        self.poll_ms = (time.monotonic() - start) * 1000
        added = self.ledger.ingest(
            self.scope, events, cursor, self.eligible, self.settings.queue_max_size
        )
        if added:
            emit("prototype.inbox", outcome="persisted")
        if not self.ledger.can_send(
            time.time(), self.settings.min_send_interval_seconds, self.settings.max_sends_per_minute
        ):
            return
        batch = self.ledger.batch(self.scope, self.settings.coalesce_window_ms)
        if not batch:
            return
        # Give short bursts a full coalescing window; native timestamps determine grouping.
        if (
            time.time() - max(e.observed_at.timestamp() for e in batch)
        ) * 1000 < self.settings.coalesce_window_ms:
            return
        generation = self.generation
        started = time.monotonic()
        with tracing_context(enabled=False):
            response = await self.graph.ainvoke(
                {
                    "events": batch,
                    "history": self.ledger.history(self.scope, batch[0].conversation_id),
                },
                config={"recursion_limit": 16, "callbacks": []},
            )
        result = response["result"]
        model_ms = (time.monotonic() - started) * 1000
        with self.send_gate:
            self.complete_turn(batch, result, generation, model_ms)

    def complete_turn(self, batch, result, generation, model_ms):
        if result.status == "ready":
            try:
                self.adapter.validate_text(result.reply_text)
            except AdapterError:
                result = result.model_copy(
                    update={
                        "status": "error",
                        "reply_text": None,
                        "reason": "output_unsupported_by_adapter",
                    }
                )
        if not self.running or generation != self.generation or time.monotonic() >= self.deadline:
            result = result.model_copy(
                update={
                    "status": "cancelled",
                    "reply_text": None,
                    "reason": "run_generation_expired",
                }
            )
        intent = None
        if (
            self.running
            and generation == self.generation
            and time.monotonic() < self.deadline
            and result.status == "ready"
        ):
            alias = next(
                c.alias for c in self.binding.contacts if c.username == batch[0].conversation_id
            )
            intent = SendIntent(
                conversation=self.adapter.resolve_conversation(alias),
                input_event_refs=tuple(e.event_id for e in batch),
                reply_text=result.reply_text,
                run_generation=generation,
                mode=self.settings.send_mode,
            )
        run_id = self.ledger.finish_model(self.scope, batch, result, intent, model_ms, self.poll_ms)
        if intent is None:
            if result.status == "error":
                self.stop(result.reason)
            return
        self.before_send()
        self.ledger.sending(intent.outbox_id, time.time())
        started = time.monotonic()
        try:
            send_result = self.adapter.send_text(intent)
        except Exception:
            send_result = SendResult(outcome="unknown", basis="sender_exception_stop_required")
        self.ledger.sent(
            self.scope, intent, batch, send_result, run_id, (time.monotonic() - started) * 1000
        )
        emit("prototype.send", outcome=send_result.outcome, reason=send_result.basis)
        if send_result.outcome == "verified_sent" or send_result.basis == "dry_run":
            self.sent_count += 1
        else:
            self.stop(send_result.basis)

    def report(self):
        report = {
            "phase": 5 if self.settings.wechat_adapter == "mac_db" else 2,
            "plan_version": "v5" if self.settings.wechat_adapter == "mac_db" else "v4",
            "platform": "macOS" if self.settings.wechat_adapter == "mac_db" else "Windows",
            "foundation": self.settings.wechat_adapter,
            "mode": self.settings.send_mode,
            "state": "running" if self.running else "stopped",
            "reason": self.reason,
            "generation": self.generation,
            "sent_this_run": self.sent_count,
            "poll_interval_seconds": self.settings.poll_interval_seconds,
            "min_send_interval_seconds": self.settings.min_send_interval_seconds,
            "model": self.settings.llm_model,
            "g2": "not_tested",
            "ledger_summary": self.ledger.summary(self.scope),
            "note": "Human verification required. Summary includes earlier runs in this scope.",
        }
        if self.settings.wechat_adapter == "mac_db":
            report.update(self.adapter.runtime_info())
        return report

    async def run(self, duration, max_replies, output):
        from wechat_reply_agent.cli import write_private

        try:
            self.start()
            self.deadline = time.monotonic() + duration
            write_private(output, self.report())
            while (
                self.running and time.monotonic() < self.deadline and self.sent_count < max_replies
            ):
                await self.tick()
                write_private(output, self.report())
                if self.running and self.sent_count < max_replies:
                    await asyncio.sleep(
                        min(
                            self.settings.poll_interval_seconds,
                            max(0, self.deadline - time.monotonic()),
                        )
                    )
            if self.running:
                self.stop("reply_limit" if self.sent_count >= max_replies else "duration_elapsed")
        except asyncio.CancelledError:
            self.stop("cancelled")
            raise
        except AdapterError as exc:
            self.stop(str(exc))
        except Exception:
            self.stop("prototype_failed_degraded")
        finally:
            write_private(output, self.report())
            if hasattr(self.adapter, "close"):
                self.adapter.close()
        return 0 if self.reason in ("reply_limit", "duration_elapsed") else 2
