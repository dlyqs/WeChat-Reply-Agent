"""All native operations run on one owned thread, including connect and diagnostics."""

import asyncio
import time


async def run_worker(service, runtime):
    max_replies = service.settings.max_replies_per_run
    runtime.start()
    with service.guard:
        if service.state != "starting":
            runtime.stop("start_cancelled")
            return
        service.state, service.reason = "running", "baseline_recorded"
        service.connected = True
        service.generation = service.repo.runtime_state(service.state, service.reason)
    last_wall, last_mono = time.time(), time.monotonic()
    while runtime.running and not service.cancel.is_set():
        wall, mono = time.time(), time.monotonic()
        if (
            abs((wall - last_wall) - (mono - last_mono)) > 5
            or mono - last_mono
            > service.settings.poll_interval_seconds + service.settings.llm_timeout_seconds + 30
        ):
            runtime.stop("desktop_resume_reconnect_required")
            break
        last_wall, last_mono = wall, mono
        service.check_database()
        await runtime.tick()
        if runtime.sent_count >= max_replies:
            runtime.stop("reply_limit")
        if runtime.running:
            # Event.wait interrupts promptly; no executor thread survives shutdown.
            service.cancel.wait(service.settings.poll_interval_seconds)
    if not runtime.running and not service.cancel.is_set():
        with service.guard:
            service.state = "stopped" if runtime.reason == "reply_limit" else "degraded"
            service.reason = runtime.reason


def execute(service, runtime):
    asyncio.run(run_worker(service, runtime))
