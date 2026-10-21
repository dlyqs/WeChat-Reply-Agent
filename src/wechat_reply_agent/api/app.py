"""Same-origin API and bundled UI. No desktop imports at application startup."""

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pydantic_settings.exceptions import SettingsError
from starlette.exceptions import HTTPException

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.runtime.service import RuntimeService
from wechat_reply_agent.settings_store import SettingsStore


def failure(code, status=400):
    return JSONResponse(
        {"code": code, "message": "操作未完成，请检查状态与配置。", "trace_id": str(uuid4())},
        status_code=status,
    )


def create_app(store=None, service=None, ui_dir=None):
    store = store or SettingsStore()
    service = service or RuntimeService(store)
    commands = threading.Lock()

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
            if request.url.path.startswith(("/api/conversations", "/api/runs", "/api/outbox")):
                service.check_database()
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
        }
        code = str(exc) if str(exc) in allowed else "operation_rejected"
        return failure(code, 404 if code == "run_not_found" else 409)

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
    def outbox(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return {"items": service.repo.outbox(limit, offset), "limit": limit, "offset": offset}

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
