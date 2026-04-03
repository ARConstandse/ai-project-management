import httpx
import pytest

from app.ai_client import AIClientError, OPENROUTER_CHAT_COMPLETIONS_URL, OpenRouterClient


def test_build_payload_uses_expected_model_and_message() -> None:
    client = OpenRouterClient(api_key="test-key")
    payload = client.build_payload("2+2")
    assert payload == {
        "model": "qwen/qwen3.6-plus-preview:free",
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
    assert "No endpoints found" in exc.value.message


def test_complete_maps_timeout_to_categorized_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(handler)
    client = OpenRouterClient(api_key="test-key", transport=transport)

    with pytest.raises(AIClientError) as exc:
        client.complete("2+2")
    assert exc.value.kind == "timeout"
