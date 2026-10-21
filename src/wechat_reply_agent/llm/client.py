"""One bounded, non-streaming compatible chat request; no provider retries or tools."""

import asyncio
from typing import Protocol
from urllib.parse import urlsplit

import httpx


class ModelError(RuntimeError):
    pass


class Model(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str: ...


class CompatibleModel:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    async def complete(self, messages):
        s = self.settings
        if not s.llm_api_key.get_secret_value():
            raise ModelError("model_key_missing")
        payload = {
            "model": s.llm_model,
            "messages": messages,
            "max_tokens": s.llm_max_output_tokens,
            "stream": False,
        }
        if urlsplit(s.llm_base_url).hostname == "api.deepseek.com":
            payload["thinking"] = {"type": "disabled"}
        try:
            async with httpx.AsyncClient(
                timeout=s.llm_timeout_seconds, transport=self.transport, follow_redirects=False
            ) as client:
                async with asyncio.timeout(s.llm_timeout_seconds):
                    response = await client.post(
                        s.llm_base_url + "/chat/completions",
                        json=payload,
                        headers={"Authorization": "Bearer " + s.llm_api_key.get_secret_value()},
                    )
            if response.status_code != 200:
                raise ModelError(f"model_http_{response.status_code}")
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ModelError("model_output_incomplete")
            message = choice["message"]
            if message.get("tool_calls") or not isinstance(message.get("content"), str):
                raise ModelError("model_output_invalid")
            return message["content"]
        except (TimeoutError, httpx.TimeoutException):
            raise ModelError("model_timeout") from None
        except ModelError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelError("model_request_failed") from None
