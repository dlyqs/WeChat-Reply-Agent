import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("wechat_reply_agent")


def emit(event: str, *, outcome: str, reason: str | None = None, trace_id: str | None = None):
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": "INFO",
                "event": event,
                "trace_id": trace_id,
                "conversation_ref": None,
                "message_ref": None,
                "adapter": "application",
                "duration_ms": None,
                "outcome": outcome,
                "reason": reason,
            },
            ensure_ascii=False,
        )
    )
