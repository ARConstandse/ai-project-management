# AI Structured Output Schema (Part 9)

This document defines the strict response contract for backend AI chat calls.

## Purpose

The AI must return:

- A user-facing response message.
- An optional full-board replacement payload.

The backend validates this schema before applying board changes.

## Request context sent to model

For each chat request, the backend includes:

- Current board JSON (`BoardModel` shape).
- Current user message.
- Conversation history (user/assistant turns).

## Required output schema (JSON Schema)

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "assistantMessage": {
      "type": "string",
      "minLength": 1
    },
    "boardUpdate": {
      "anyOf": [
        { "type": "null" },
        {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "columns": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "id": { "type": "string", "minLength": 1 },
                  "title": { "type": "string" },
                  "cardIds": {
                    "type": "array",
                    "items": { "type": "string", "minLength": 1 }
                  }
                },
                "required": ["id", "title", "cardIds"]
              }
            },
            "cards": {
              "type": "object",
              "additionalProperties": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "id": { "type": "string", "minLength": 1 },
                  "title": { "type": "string" },
                  "details": { "type": "string" }
                },
                "required": ["id", "title", "details"]
              }
            }
          },
          "required": ["columns", "cards"]
        }
      ]
    }
  },
  "required": ["assistantMessage", "boardUpdate"]
}
```

## Validation and safety rules

- Backend enforces strict parsing and schema validation.
- `boardUpdate` is applied only when present and valid.
- Board consistency checks are enforced (`cards` keys must match `card.id`; all `column.cardIds` must exist in `cards`).
- Invalid outputs return a safe error response and do not persist board changes.
