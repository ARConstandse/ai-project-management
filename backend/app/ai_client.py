from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "qwen/qwen3.6-plus-preview:free"
DEFAULT_TIMEOUT_SECONDS = 15.0


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

        raise AIClientError("invalid_response", "Missing assistant content.")

    def complete(self, prompt: str) -> str:
        payload = self.build_payload(prompt)
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

        return self.parse_response_text(data)

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
    return OpenRouterClient(api_key=api_key)
