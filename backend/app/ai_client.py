from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

OPENROUTER_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 15.0
STRUCTURED_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assistantMessage": {"type": "string", "minLength": 1},
        "boardUpdate": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "id": {"type": "string", "minLength": 1},
                                    "title": {"type": "string"},
                                    "cardIds": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                },
                                "required": ["id", "title", "cardIds"],
                            },
                        },
                        "cards": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "id": {"type": "string", "minLength": 1},
                                    "title": {"type": "string"},
                                    "details": {"type": "string"},
                                },
                                "required": ["id", "title", "details"],
                            },
                        },
                    },
                    "required": ["columns", "cards"],
                },
            ]
        },
    },
    "required": ["assistantMessage", "boardUpdate"],
}


@dataclass
class AIClientError(Exception):
    kind: str
    message: str

    def to_http(self) -> tuple[int, dict[str, str]]:
        if self.kind == "configuration":
            return 500, {
                "error": "ai_not_configured",
                "message": "AI provider is not configured.",
            }
        if self.kind == "timeout":
            return 504, {
                "error": "ai_timeout",
                "message": "AI provider timed out.",
            }
        if self.kind == "auth":
            return 502, {
                "error": "ai_upstream_auth_error",
                "message": "AI provider authentication failed.",
            }
        if self.kind == "rate_limit":
            return 502, {
                "error": "ai_upstream_rate_limited",
                "message": "AI provider rate limited the request.",
            }
        if self.kind == "model_unavailable":
            return 502, {
                "error": "ai_model_unavailable",
                "message": "Configured AI model is unavailable at provider.",
            }
        if self.kind == "network":
            return 502, {
                "error": "ai_network_error",
                "message": "Could not reach AI provider.",
            }
        if self.kind == "invalid_response":
            return 502, {
                "error": "ai_invalid_response",
                "message": "AI provider returned an invalid response.",
            }
        return 502, {
            "error": "ai_upstream_error",
            "message": "AI provider returned an error.",
        }


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str = OPENROUTER_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def build_payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

    def build_structured_chat_payload(
        self,
        board_payload: dict[str, Any],
        user_message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        context_blob = {
            "conversationHistory": history,
            "userMessage": user_message,
            "board": board_payload,
        }
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a project management assistant. "
                        "Always return ONLY valid JSON matching the provided schema."
                    ),
                },
                {"role": "user", "content": json.dumps(context_blob, separators=(",", ":"))},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "pm_ai_chat_output",
                    "strict": True,
                    "schema": STRUCTURED_OUTPUT_SCHEMA,
                },
            },
        }

    def parse_response_text(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIClientError("invalid_response", "Missing choices array.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AIClientError("invalid_response", "Choice is not an object.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise AIClientError("invalid_response", "Missing message object.")

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                    continue
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text

        raise AIClientError("invalid_response", "Missing assistant content.")

    def complete(self, prompt: str) -> str:
        payload = self.build_payload(prompt)
        data = self._post_payload(payload)
        return self.parse_response_text(data)

    def complete_structured_chat(
        self,
        board_payload: dict[str, Any],
        user_message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        payload = self.build_structured_chat_payload(
            board_payload=board_payload,
            user_message=user_message,
            history=history,
        )
        data = self._post_payload(payload)
        content = self.parse_response_text(data)
        parsed = self._parse_json_object_from_text(content)
        if not isinstance(parsed, dict):
            raise AIClientError(
                "invalid_response", "Structured output root was not an object."
            )
        return parsed

    def _parse_json_object_from_text(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass

        # Some providers prepend prose or wrap JSON in ```json fences.
        code_fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", content)
        if code_fence_match:
            candidate = code_fence_match.group(1)
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except ValueError:
                pass

        first = content.find("{")
        last = content.rfind("}")
        if first != -1 and last != -1 and first < last:
            candidate = content[first : last + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except ValueError:
                pass

        raise AIClientError("invalid_response", "Structured output was not valid JSON.")

    def _post_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    OPENROUTER_CHAT_COMPLETIONS_URL, json=payload, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise AIClientError("timeout", "Upstream call timed out.") from exc
        except httpx.HTTPError as exc:
            raise AIClientError("network", "Network error calling upstream.") from exc

        if response.status_code >= 400:
            upstream_message = self._extract_upstream_message(response)
            if response.status_code in (401, 403):
                raise AIClientError("auth", "Upstream auth failed.")
            if response.status_code == 429:
                raise AIClientError("rate_limit", "Upstream rate limit.")
            if response.status_code == 404:
                raise AIClientError("model_unavailable", upstream_message)
            raise AIClientError("upstream", upstream_message)

        try:
            data = response.json()
        except ValueError as exc:
            raise AIClientError("invalid_response", "Response was not valid JSON.") from exc

        if not isinstance(data, dict):
            raise AIClientError("invalid_response", "Top-level JSON was not an object.")
        return data

    def _extract_upstream_message(self, response: httpx.Response) -> str:
        default = f"Upstream returned {response.status_code}."
        try:
            data = response.json()
        except ValueError:
            return default

        if not isinstance(data, dict):
            return default

        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return default


def openrouter_client_from_env() -> OpenRouterClient:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise AIClientError("configuration", "OPENROUTER_API_KEY is not set.")
    model = os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODEL
    # Convenience for common shorthand like `qwen3.6-plus:free`.
    if "/" not in model and model.lower().startswith("qwen"):
        model = f"qwen/{model}"
    return OpenRouterClient(api_key=api_key, model=model)
