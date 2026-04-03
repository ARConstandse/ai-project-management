import type { BoardData } from "@/lib/kanban";

const BOARD_ENDPOINT = "/api/board";
const CHAT_ENDPOINT = "/api/ai/chat";

export type ChatHistoryTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ChatResponse = {
  assistantMessage: string;
  boardUpdate: BoardData | null;
};

const parseApiError = async (response: Response): Promise<string> => {
  const fallback = `Request failed (${response.status})`;
  try {
    const payload = (await response.json()) as {
      detail?: string | { message?: string };
    };
    if (typeof payload?.detail === "string") {
      return payload.detail;
    }
    if (typeof payload?.detail?.message === "string") {
      return payload.detail.message;
    }
    return fallback;
  } catch {
    return fallback;
  }
};

export const fetchBoard = async (): Promise<BoardData> => {
  const response = await fetch(BOARD_ENDPOINT, {
    method: "GET",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BoardData;
};

export const saveBoard = async (board: BoardData): Promise<BoardData> => {
  const response = await fetch(BOARD_ENDPOINT, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(board),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as BoardData;
};

export const sendChatMessage = async (
  message: string,
  history: ChatHistoryTurn[]
): Promise<ChatResponse> => {
  const response = await fetch(CHAT_ENDPOINT, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ message, history }),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return (await response.json()) as ChatResponse;
};

