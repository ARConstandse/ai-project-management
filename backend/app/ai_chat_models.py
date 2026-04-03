from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .kanban_models import BoardModel


class ConversationTurnModel(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AIChatRequestModel(BaseModel):
    message: str = Field(min_length=1)
    history: list[ConversationTurnModel] = Field(default_factory=list)


class AIChatStructuredOutputModel(BaseModel):
    assistantMessage: str = Field(min_length=1)
    boardUpdate: BoardModel | None


class AIChatResponseModel(BaseModel):
    assistantMessage: str
    boardUpdate: BoardModel | None
