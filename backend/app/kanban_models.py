from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CardModel(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(max_length=4000)


class ColumnModel(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=100)
    cardIds: list[str] = Field(default_factory=list)


class BoardModel(BaseModel):
    columns: list[ColumnModel]
    cards: dict[str, CardModel]

    @model_validator(mode="after")
    def validate_consistency(self) -> "BoardModel":
        # Ensure card ids match their map keys.
        for card_key, card in self.cards.items():
            if card.id != card_key:
                raise ValueError(f"cards.{card_key}.id must match its key")

        # Ensure every referenced cardId exists in `cards`.
        for col in self.columns:
            for card_id in col.cardIds:
                if card_id not in self.cards:
                    raise ValueError(
                        f"Unknown cardId '{card_id}' referenced by column '{col.id}'"
                    )

        return self

