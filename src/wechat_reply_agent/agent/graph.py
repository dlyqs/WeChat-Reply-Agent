"""Minimal LangGraph: input filter -> bounded context -> model -> output validation."""

import asyncio
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import Field

from wechat_reply_agent.domain.messages import Contract, Direction, InboundEvent
from wechat_reply_agent.llm.client import ModelError


class AgentResult(Contract):
    status: str
    reply_text: str | None = None
    reason: str
    calls: int = 0
    duration_ms: float = Field(default=0, ge=0)


class State(TypedDict, total=False):
    events: list[InboundEvent]
    history: list[dict[str, str]]
    messages: list[dict[str, str]]
    result: AgentResult
    text: str


def input_cost(messages):
    # UTF-8 bytes conservatively bound tokens; no dependency on a provider tokenizer.
    return sum(len(m["content"].encode("utf-8")) + 16 for m in messages) + 16


def create_graph(settings, model):
    def filter_input(state):
        events = state["events"]
        if not events or any(
            e.direction != Direction.INCOMING
            or e.type != "text"
            or e.confidence != 1
            or not e.text
            or not e.source_message_id
            for e in events
        ):
            return {"result": AgentResult(status="filtered", reason="input_filtered")}
        return {}

    def context(state):
        base = [{"role": "system", "content": settings.agent_persona}]
        current = {"role": "user", "content": "\n".join(e.text for e in state["events"])}
        history = list(state.get("history", []))
        while history and input_cost(base + history + [current]) > settings.llm_max_input_tokens:
            history = history[2:]
        messages = base + history + [current]
        if input_cost(messages) > settings.llm_max_input_tokens:
            return {"result": AgentResult(status="error", reason="input_budget_exceeded")}
        return {"messages": messages}

    async def generate(state):
        start = time.monotonic()
        try:
            text = await asyncio.wait_for(
                model.complete(state["messages"]), timeout=settings.llm_timeout_seconds
            )
            return {"text": text}
        except (TimeoutError, ModelError) as exc:
            reason = str(exc) if isinstance(exc, ModelError) else "model_timeout"
        except Exception:
            reason = "model_failed"
        return {
            "result": AgentResult(
                status="error",
                reason=reason,
                calls=1,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        }

    def validate(state):
        text = state["text"].strip()
        if (
            not text
            or len(text) > settings.max_reply_characters
            or any(ord(c) < 32 and c != "\n" for c in text)
        ):
            return {"result": AgentResult(status="error", reason="output_rejected", calls=1)}
        return {"result": AgentResult(status="ready", reason="validated", reply_text=text, calls=1)}

    def route(state, next_node):
        return END if state.get("result") else next_node

    graph = StateGraph(State)
    graph.add_node("filter", filter_input)
    graph.add_node("context", context)
    graph.add_node("model", generate)
    graph.add_node("validate", validate)
    graph.add_edge(START, "filter")
    graph.add_conditional_edges("filter", lambda s: route(s, "context"))
    graph.add_conditional_edges("context", lambda s: route(s, "model"))
    graph.add_conditional_edges("model", lambda s: route(s, "validate"))
    graph.add_edge("validate", END)
    return graph.compile()
