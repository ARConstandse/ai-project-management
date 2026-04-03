import pytest
from pydantic import ValidationError

from app.ai_chat_models import AIChatStructuredOutputModel


def test_structured_output_accepts_response_only_payload() -> None:
    parsed = AIChatStructuredOutputModel.model_validate(
        {"assistantMessage": "No board changes needed.", "boardUpdate": None}
    )
    assert parsed.assistantMessage == "No board changes needed."
    assert parsed.boardUpdate is None


def test_structured_output_accepts_response_and_board_update() -> None:
    parsed = AIChatStructuredOutputModel.model_validate(
        {
            "assistantMessage": "Moved the card.",
            "boardUpdate": {
                "columns": [{"id": "col-1", "title": "Todo", "cardIds": ["card-1"]}],
                "cards": {
                    "card-1": {"id": "card-1", "title": "Task", "details": "Details"}
                },
            },
        }
    )
    assert parsed.boardUpdate is not None
    assert parsed.boardUpdate.columns[0].cardIds == ["card-1"]


def test_structured_output_rejects_inconsistent_board_update() -> None:
    with pytest.raises(ValidationError):
        AIChatStructuredOutputModel.model_validate(
            {
                "assistantMessage": "Invalid update",
                "boardUpdate": {
                    "columns": [
                        {
                            "id": "col-1",
                            "title": "Todo",
                            "cardIds": ["missing-card"],
                        }
                    ],
                    "cards": {},
                },
            }
        )
