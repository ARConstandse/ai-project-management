import httpx
import pytest

from app.ai_client import (
    AIClientError,
    OPENROUTER_CHAT_COMPLETIONS_URL,
    OPENROUTER_MODEL,
    OpenRouterClient,
    openrouter_client_from_env,
)


def test_build_payload_uses_expected_model_and_message() -> None:
    client = OpenRouterClient(api_key="test-key")
    payload = client.build_payload("2+2")
    assert payload == {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": "2+2"}],
    }


def test_parse_response_text_reads_first_choice_message() -> None:
    client = OpenRouterClient(api_key="test-key")
    parsed = client.parse_response_text(
        {"choices": [{"message": {"content": "4"}}], "id": "abc"}
    )
    assert parsed == "4"


def test_complete_posts_to_openrouter_and_returns_response_text() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = request.read().decode("utf-8")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "The answer is 4."}}]}
        )

    transport = httpx.MockTransport(handler)
    client = OpenRouterClient(api_key="test-key", transport=transport)
    response_text = client.complete("2+2")

    assert response_text == "The answer is 4."
    assert captured["url"] == OPENROUTER_CHAT_COMPLETIONS_URL
    assert captured["auth"] == "Bearer test-key"
    assert '"content":"2+2"' in str(captured["body"])


def test_complete_maps_rate_limit_to_categorized_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"error": {}}))
    client = OpenRouterClient(api_key="test-key", transport=transport)

    with pytest.raises(AIClientError) as exc:
        client.complete("2+2")
    assert exc.value.kind == "rate_limit"


def test_complete_maps_model_not_found_to_model_unavailable_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            404, json={"error": {"message": "No endpoints found for model."}}
        )
    )
    client = OpenRouterClient(api_key="test-key", transport=transport)

    with pytest.raises(AIClientError) as exc:
        client.complete("2+2")
    assert exc.value.kind == "model_unavailable"


def test_complete_maps_timeout_to_categorized_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(handler)
    client = OpenRouterClient(api_key="test-key", transport=transport)

    with pytest.raises(AIClientError) as exc:
        client.complete("2+2")
    assert exc.value.kind == "timeout"


def test_build_structured_chat_payload_includes_context_and_schema() -> None:
    client = OpenRouterClient(api_key="test-key")
    payload = client.build_structured_chat_payload(
        board_payload={"columns": [], "cards": {}},
        user_message="Move card-1 to done",
        history=[{"role": "user", "content": "Hi"}],
    )

    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True


def test_complete_structured_chat_parses_json_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"assistantMessage":"Done","boardUpdate":null}'
                        }
                    }
                ]
            },
        )

    client = OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))
    parsed = client.complete_structured_chat(
        board_payload={"columns": [], "cards": {}},
        user_message="Hello",
        history=[],
    )
    assert parsed == {"assistantMessage": "Done", "boardUpdate": None}


def test_complete_structured_chat_parses_fenced_json_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Here is the result:\n```json\n{\"assistantMessage\":\"Done\",\"boardUpdate\":null}\n```"
                        }
                    }
                ]
            },
        )

    client = OpenRouterClient(api_key="test-key", transport=httpx.MockTransport(handler))
    parsed = client.complete_structured_chat(
        board_payload={"columns": [], "cards": {}},
        user_message="Hello",
        history=[],
    )
    assert parsed == {"assistantMessage": "Done", "boardUpdate": None}


def test_openrouter_client_from_env_uses_model_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3.6-plus:free")
    client = openrouter_client_from_env()
    assert client.model == "qwen/qwen3.6-plus:free"


def test_openrouter_client_from_env_normalizes_qwen_shorthand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen3.6-plus:free")
    client = openrouter_client_from_env()
    assert client.model == "qwen/qwen3.6-plus:free"


def test_parse_response_text_accepts_content_parts_array() -> None:
    client = OpenRouterClient(api_key="test-key")
    parsed = client.parse_response_text(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "First line"},
                            {"type": "text", "text": "Second line"},
                        ]
                    }
                }
            ]
        }
    )
    assert parsed == "First line\nSecond line"
