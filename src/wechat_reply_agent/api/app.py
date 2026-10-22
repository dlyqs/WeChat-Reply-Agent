"""Same-origin API and bundled UI. No desktop imports at application startup."""

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langsmith import tracing_context
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings.exceptions import SettingsError
from starlette.exceptions import HTTPException

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.agent.graph import create_graph
from wechat_reply_agent.agent.personas import PRESETS
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import InboundEvent
from wechat_reply_agent.knowledge.demo import demo_catalog, seed_demo
from wechat_reply_agent.knowledge.store import KnowledgeStore
from wechat_reply_agent.llm.client import CompatibleModel, ModelError
from wechat_reply_agent.memory.store import MemoryStore
from wechat_reply_agent.runtime.service import RuntimeService
from wechat_reply_agent.settings_store import SettingsStore


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=48_000)
    base_id: str = Field(default="personal", min_length=1, max_length=64)


class BaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=300)


class BaseChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=300)
    enabled: bool | None = None


class ClearHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str
    scope: str | None = Field(default=None, min_length=1, max_length=500)
    conversation: str | None = Field(default=None, min_length=1, max_length=200)
    forget_memories: bool = False


class ModelTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_base_url: str | None = Field(default=None, max_length=500)
    llm_model: str | None = Field(default=None, max_length=100)
    llm_api_key: str | None = Field(default=None, max_length=500)


class PreviewMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    base_id: str = Field(min_length=1, max_length=64)
    history: list[PreviewMessage] = Field(default_factory=list, max_length=12)


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str = Field(min_length=1, max_length=500)
    contact: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=200)


def failure(code, status=400):
    return JSONResponse(
        {"code": code, "message": "操作未完成，请检查状态与配置。", "trace_id": str(uuid4())},
        status_code=status,
    )


def create_app(store=None, service=None, ui_dir=None):
    store = store or SettingsStore()
    service = service or RuntimeService(store)
    commands = threading.Lock()
    knowledge = KnowledgeStore(service.path)
    memory = MemoryStore(service.path)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.state.store = store
    port = store.settings.app_port
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    origins = {"http://" + host for host in hosts}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.headers.get("host", "").lower() not in hosts:
            return failure("host_rejected", 403)
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return failure("origin_rejected", 403)
        if request.method not in ("GET", "HEAD"):
            if origin not in origins or request.headers.get("x-wechat-agent") != "1":
                return failure("write_source_rejected", 403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return failure("json_required", 415)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return failure("request_too_large", 413)
            request._body = bytes(body)
        try:
            if request.url.path.startswith(
                (
                    "/api/conversations",
                    "/api/runs",
                    "/api/outbox",
                    "/api/knowledge",
                    "/api/memories",
                    "/api/history",
                    "/api/dashboard",
                )
            ):
                service.check_database(check_sources=False)
            response = await call_next(request)
        except Exception:
            return failure("operation_failed", 500)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.exception_handler(AdapterError)
    async def adapter_error(request, exc):
        # Public errors originate in this application's control/repository validation.
        allowed = {
            "runtime_transition_invalid",
            "worker_still_stopping",
            "nonempty_allowlist_required",
            "model_key_missing",
            "poll_minimum_10_seconds",
            "g1_g2_reports_required",
            "application_database_replaced",
            "run_not_found",
            "stop_before_diagnostic",
            "settings_field_not_editable",
            "settings_invalid",
            "settings_field_not_applicable",
            "resolution_invalid",
            "unknown_outbox_missing",
            "stop_before_settings",
            "stop_before_resolution",
            "stop_before_content_change",
            "knowledge_document_invalid",
            "knowledge_document_too_large",
            "knowledge_capacity_reached",
            "knowledge_document_not_found",
            "memory_contact_not_found",
            "memory_fact_invalid",
            "memory_capacity_reached",
            "knowledge_base_not_found",
            "knowledge_base_invalid",
            "knowledge_base_capacity_reached",
            "default_knowledge_base_required",
            "history_selection_invalid",
            "history_confirmation_required",
            "history_unresolved_outbox",
        }
        code = str(exc) if str(exc) in allowed else "operation_rejected"
        return failure(code, 404 if code.endswith("_not_found") else 409)

    async def invalid(request, exc):
        return failure("request_invalid", 422)

    for error_type in (RequestValidationError, ValidationError, SettingsError):
        app.add_exception_handler(error_type, invalid)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return failure(
            "route_not_found" if exc.status_code == 404 else "request_rejected", exc.status_code
        )

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "foundation": store.settings.wechat_adapter,
            "runtime": service.snapshot(),
            "diagnostics": "explicit_post_required",
        }

    @app.get("/api/runtime")
    def runtime():
        return service.snapshot()

    @app.get("/api/setup")
    def setup():
        return service.setup()

    @app.get("/api/dashboard")
    def dashboard():
        return service.repo.dashboard()

    @app.get("/api/agent/presets")
    def presets():
        return {"items": PRESETS}

    @app.post("/api/model/test")
    def test_model(body: ModelTestInput):
        with commands:
            service.require_idle()
            changes = body.model_dump(exclude_none=True)
            if not changes.get("llm_api_key"):
                changes.pop("llm_api_key", None)
            settings = Settings.model_validate(store.settings.model_dump() | changes)
            started = time.monotonic()
            try:
                asyncio.run(
                    CompatibleModel(settings).complete(
                        [
                            {"role": "system", "content": "This is a connection check. Reply OK."},
                            {"role": "user", "content": "OK?"},
                        ]
                    )
                )
            except ModelError as exc:
                return failure(str(exc), 400)
            return {"ok": True, "duration_ms": round((time.monotonic() - started) * 1000)}

    @app.post("/api/history/clear")
    def clear_history(body: ClearHistoryInput):
        with commands:
            service.require_idle()
            if body.confirmation != "清除":
                raise AdapterError("history_confirmation_required")
            return service.repo.clear_history(body.scope, body.conversation, body.forget_memories)

    @app.post("/api/agent/preview")
    def preview_reply(body: PreviewInput):
        with commands:
            service.require_idle()
            if not store.settings.llm_api_key.get_secret_value():
                raise AdapterError("model_key_missing")
            if not any(b["id"] == body.base_id for b in knowledge.bases()):
                raise AdapterError("knowledge_base_not_found")
            graph = create_graph(
                store.settings,
                service.model_factory(store.settings),
                KnowledgeStore(service.path, body.base_id),
            )
            event = InboundEvent(
                conversation_id="preview",
                account_ref="preview",
                account_generation="preview",
                occurrence_ref="preview",
                source_message_id=uuid4().hex,
                direction="incoming",
                text=body.question,
                confidence=1,
            )
            with tracing_context(enabled=False):
                result = asyncio.run(
                    graph.ainvoke(
                        {
                            "events": [event],
                            "history": [m.model_dump() for m in body.history],
                        },
                        config={"recursion_limit": 16, "callbacks": []},
                    )
                )["result"]
            return result.model_dump() | {"sent_to_wechat": False, "preview_only": True}

    @app.post("/api/runtime/{action}")
    def transition(action: str):
        with commands:
            if action == "start":
                return service.start()
            if action == "resume":
                return service.start(resume=True)
            if action in ("pause", "stop"):
                return service.halt(pause=action == "pause")
            raise AdapterError("runtime_transition_invalid")

    @app.get("/api/conversations")
    def conversations(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return {
            "items": service.repo.conversations(limit, offset),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/conversations/{conversation_id}/messages")
    def messages(
        conversation_id: str,
        scope: str = Query(min_length=1),
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        return {
            "items": service.repo.messages(conversation_id, scope, limit, offset),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/runs")
    def runs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return {"items": service.repo.runs(limit, offset), "limit": limit, "offset": offset}

    @app.get("/api/runs/{trace_id}")
    def run(trace_id: int):
        return service.repo.run(trace_id)

    @app.get("/api/outbox")
    def outbox(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        scope: str | None = Query(default=None, max_length=500),
        conversation: str | None = Query(default=None, max_length=200),
    ):
        return {
            "items": service.repo.outbox(limit, offset, scope, conversation),
            "limit": limit,
            "offset": offset,
        }

    @app.post("/api/outbox/{outbox_id}/resolve")
    def resolve(outbox_id: str, body: Annotated[dict, Body()]):
        with commands:
            if service.snapshot()["state"] not in ("stopped", "paused", "degraded"):
                raise AdapterError("stop_before_resolution")
            if set(body) != {"resolution"}:
                raise AdapterError("resolution_invalid")
            service.resolve(outbox_id, body["resolution"])
            return {"id": outbox_id, "resolution": body["resolution"]}

    @app.get("/api/settings")
    def settings():
        return store.public()

    @app.patch("/api/settings")
    def save(body: Annotated[dict, Body()]):
        with commands:
            if service.snapshot()["state"] not in ("stopped", "paused", "degraded"):
                raise AdapterError("stop_before_settings")
            return store.patch(body)

    @app.post("/api/diagnostics")
    def diagnostics():
        with commands:
            return service.diagnostic()

    def require_content_edit():
        service.require_idle()

    @app.get("/api/knowledge/bases")
    def knowledge_bases():
        return {"items": knowledge.bases(), "demo": demo_catalog()}

    @app.post("/api/knowledge/bases")
    def create_base(body: BaseInput):
        with commands:
            require_content_edit()
            return knowledge.create_base(body.name, body.description)

    @app.patch("/api/knowledge/bases/{base_id}")
    def update_base(base_id: str, body: BaseChange):
        with commands:
            require_content_edit()
            return knowledge.update_base(base_id, body.model_dump(exclude_none=True))

    @app.delete("/api/knowledge/bases/{base_id}")
    def delete_base(base_id: str):
        with commands:
            require_content_edit()
            knowledge.delete_base(base_id)
            return {"id": base_id, "deleted": True}

    @app.post("/api/knowledge/demo")
    def restore_demo():
        with commands:
            require_content_edit()
            seed_demo(service.path, force=True, activate=True)
            return {"items": knowledge.bases(), "demo": demo_catalog()}

    @app.get("/api/knowledge/documents")
    def documents(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        base_id: str | None = Query(default=None, max_length=64),
    ):
        return {
            "items": knowledge.documents(limit, offset, base_id),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/knowledge/documents/{document_id}")
    def document(document_id: str):
        return knowledge.document(document_id)

    @app.post("/api/knowledge/documents")
    def import_document(body: DocumentInput):
        with commands:
            require_content_edit()
            return knowledge.import_text(body.name, body.content, body.base_id)

    @app.delete("/api/knowledge/documents/{document_id}")
    def delete_document(document_id: str, base_id: str | None = Query(default=None, max_length=64)):
        with commands:
            require_content_edit()
            knowledge.delete(document_id, base_id)
            return {"id": document_id, "deleted": True}

    @app.get("/api/knowledge/search")
    def search_knowledge(
        q: str = Query(min_length=1, max_length=2000),
        base_id: str | None = Query(default=None, max_length=64),
    ):
        return {"items": knowledge.search(q, base_id=base_id)}

    @app.get("/api/memories/contacts")
    def memory_contacts():
        return {"items": memory.contacts()}

    @app.get("/api/memories")
    def memories(
        scope: str = Query(min_length=1, max_length=500),
        contact: str = Query(min_length=1, max_length=200),
    ):
        return {"items": memory.read(scope, contact)}

    @app.put("/api/memories")
    def change_memory(body: MemoryInput):
        with commands:
            require_content_edit()
            memory.change(body.scope, body.contact, body.key, body.value)
            return {"key": body.key, "saved": True}

    @app.delete("/api/memories")
    def forget_memory(
        scope: str = Query(min_length=1, max_length=500),
        contact: str = Query(min_length=1, max_length=200),
        key: str = Query(min_length=1, max_length=40),
    ):
        with commands:
            require_content_edit()
            memory.change(scope, contact, key, None)
            return {"key": key, "deleted": True}

    ui = Path(ui_dir) if ui_dir else Path(__file__).resolve().parent.parent / "web"
    if (ui / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=ui / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (ui / "index.html").is_file():
            return failure("ui_build_required", 503)
        return FileResponse(ui / "index.html")

    @app.get("/THIRD_PARTY_LICENSES.txt")
    def dependency_licenses():
        if not (ui / "THIRD_PARTY_LICENSES.txt").is_file():
            return failure("ui_build_required", 503)
        return FileResponse(ui / "THIRD_PARTY_LICENSES.txt", media_type="text/plain")

    return app
