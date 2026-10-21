"""All native operations run on one owned thread, including connect and diagnostics."""

import asyncio


async def run_worker(service, runtime):
    runtime.start()
    with service.guard:
        if service.state != "starting":
            runtime.stop("start_cancelled")
            return
        service.state, service.reason = "running", "baseline_recorded"
        service.connected = True
        service.generation = service.repo.runtime_state(service.state, service.reason)
    while runtime.running and not service.cancel.is_set():
        service.check_database()
        await runtime.tick()
        if runtime.sent_count >= 3:
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
