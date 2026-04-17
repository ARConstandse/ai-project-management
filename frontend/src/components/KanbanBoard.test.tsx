import React from "react";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DragEndEvent, DragOverEvent } from "@dnd-kit/core";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const dndHandlers: {
  onDragOver?: (event: DragOverEvent) => void;
  onDragEnd?: (event: DragEndEvent) => void;
} = {};

vi.mock("@dnd-kit/core", async () => {
  const actual = await vi.importActual<typeof import("@dnd-kit/core")>("@dnd-kit/core");
  const RealDndContext = actual.DndContext;
  return {
    ...actual,
    DndContext: (props: any) => {
      dndHandlers.onDragOver = props.onDragOver;
      dndHandlers.onDragEnd = props.onDragEnd;
      return React.createElement(RealDndContext, props);
    },
  };
});

const makeDragEvent = (activeId: string, overId: string) =>
  ({
    active: { id: activeId },
    over: { id: overId },
    collisions: [],
    delta: { x: 0, y: 0 },
    activatorEvent: new Event("pointer"),
  }) as unknown as DragOverEvent & DragEndEvent;

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];
const mockFetch = vi.fn();
let mockBoard = structuredClone(initialData);

const mockFetchResponse = (payload: unknown) => ({
  ok: true,
  status: 200,
  json: async () => payload,
});

const renderBoard = async () => {
  render(<KanbanBoard />);
  await waitFor(() =>
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/board",
      expect.objectContaining({ method: "GET" })
    )
  );
  await waitFor(() =>
    expect(screen.queryByText("Loading board...")).not.toBeInTheDocument()
  );
};

describe("KanbanBoard", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockBoard = structuredClone(initialData);
    mockFetch.mockImplementation(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = init?.method ?? "GET";
        if (url === "/api/board" && method === "GET") {
          return mockFetchResponse(mockBoard);
        }
        if (url === "/api/board" && method === "PUT") {
          if (typeof init?.body === "string") {
            mockBoard = JSON.parse(init.body);
          }
          return mockFetchResponse(mockBoard);
        }
        if (url === "/api/ai/chat" && method === "POST") {
          const body = JSON.parse((init?.body as string) ?? "{}") as {
            message?: string;
          };
          return mockFetchResponse({
            assistantMessage: `Echo: ${body.message ?? ""}`,
            boardUpdate: null,
          });
        }
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: "Not Found" }),
        };
      }
    );
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders five columns", async () => {
    await renderBoard();
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
    expect(screen.getByRole("link", { name: /log out/i })).toHaveAttribute(
      "href",
      "/logout"
    );
  });

  it("loads board data from backend api", async () => {
    await renderBoard();
    expect(screen.getByText("Backlog")).toBeInTheDocument();
  });

  it("renames a column", async () => {
    await renderBoard();
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
  });

  it("adds and removes a card", async () => {
    await renderBoard();
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(within(column).getByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
  });

  it("persists board changes through backend api", async () => {
    await renderBoard();
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "API Saved Name");

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/board",
        expect.objectContaining({ method: "PUT" })
      )
    );
  });

  it("renders chat sidebar and returns assistant response", async () => {
    await renderBoard();
    expect(screen.getByRole("heading", { name: /board chat/i })).toBeInTheDocument();

    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "What should I do next?");
    await userEvent.click(screen.getByRole("button", { name: /send to ai/i }));

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/ai/chat",
        expect.objectContaining({ method: "POST" })
      )
    );
    await waitFor(() =>
      expect(screen.getByText("Echo: What should I do next?")).toBeInTheDocument()
    );
  });

  it("moves a card between columns via drag and drop", async () => {
    await renderBoard();

    const discoveryColumn = screen.getByTestId("column-col-discovery");
    const progressColumn = screen.getByTestId("column-col-progress");

    expect(within(progressColumn).getByTestId("card-card-4")).toBeInTheDocument();
    expect(within(discoveryColumn).queryByTestId("card-card-4")).not.toBeInTheDocument();

    act(() => {
      dndHandlers.onDragOver?.(makeDragEvent("card-4", "col-discovery"));
    });

    act(() => {
      dndHandlers.onDragEnd?.(makeDragEvent("card-4", "col-discovery"));
    });

    await waitFor(() => {
      expect(within(discoveryColumn).getByTestId("card-card-4")).toBeInTheDocument();
      expect(within(progressColumn).queryByTestId("card-card-4")).not.toBeInTheDocument();
    });
  });

  it("shows error when board save fails", async () => {
    await renderBoard();

    mockFetch.mockImplementation(async (input: string | URL | Request, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";
      if (url === "/api/board" && method === "GET") {
        return mockFetchResponse(mockBoard);
      }
      if (url === "/api/board" && method === "PUT") {
        return { ok: false, status: 500, json: async () => ({ detail: "Internal Server Error" }) };
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not Found" }) };
    });

    const column = screen.getAllByTestId(/column-/i)[0];
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Trigger save error");

    await waitFor(() =>
      expect(screen.getByText("Could not save board changes.")).toBeInTheDocument()
    );
  });

  it("shows retry button when board save fails", async () => {
    await renderBoard();

    mockFetch.mockImplementation(async (input: string | URL | Request, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";
      if (url === "/api/board" && method === "GET") return mockFetchResponse(mockBoard);
      if (url === "/api/board" && method === "PUT") {
        return { ok: false, status: 500, json: async () => ({ detail: "Error" }) };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    });

    const column = screen.getAllByTestId(/column-/i)[0];
    await userEvent.clear(within(column).getByLabelText("Column title"));
    await userEvent.type(within(column).getByLabelText("Column title"), "Error trigger");

    await waitFor(() => expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument());
  });

  it("shows error when AI chat request fails", async () => {
    await renderBoard();

    mockFetch.mockImplementation(async (input: string | URL | Request, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";
      if (url === "/api/board" && method === "GET") return mockFetchResponse(mockBoard);
      if (url === "/api/board" && method === "PUT") return mockFetchResponse(mockBoard);
      if (url === "/api/ai/chat" && method === "POST") {
        return {
          ok: false,
          status: 504,
          json: async () => ({ detail: { message: "AI provider timed out." } }),
        };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    });

    await userEvent.type(screen.getByLabelText("Message"), "trigger error");
    await userEvent.click(screen.getByRole("button", { name: /send to ai/i }));

    await waitFor(() =>
      expect(screen.getByText("AI provider timed out.")).toBeInTheDocument()
    );
  });

  it("shows error when board fails to load", async () => {
    mockFetch.mockImplementation(async (input: string | URL | Request, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";
      if (url === "/api/board" && method === "GET") {
        return { ok: false, status: 401, json: async () => ({ detail: "Unauthorized" }) };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    });

    render(<KanbanBoard />);
    await waitFor(() =>
      expect(screen.getByText("Unable to load board from server. Please refresh the page.")).toBeInTheDocument()
    );
  });

  it("applies board update returned by AI chat", async () => {
    mockFetch.mockImplementation(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        const method = init?.method ?? "GET";
        if (url === "/api/board" && method === "GET") {
          return mockFetchResponse(mockBoard);
        }
        if (url === "/api/board" && method === "PUT") {
          if (typeof init?.body === "string") {
            mockBoard = JSON.parse(init.body);
          }
          return mockFetchResponse(mockBoard);
        }
        if (url === "/api/ai/chat" && method === "POST") {
          return mockFetchResponse({
            assistantMessage: "Done",
            boardUpdate: {
              ...mockBoard,
              cards: {
                ...mockBoard.cards,
                "card-1": {
                  ...mockBoard.cards["card-1"],
                  title: "AI Updated Title",
                },
              },
            },
          });
        }
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: "Not Found" }),
        };
      }
    );

    await renderBoard();
    await userEvent.type(screen.getByLabelText("Message"), "Rename card 1");
    await userEvent.click(screen.getByRole("button", { name: /send to ai/i }));

    await waitFor(() =>
      expect(screen.getByText("AI Updated Title")).toBeInTheDocument()
    );
    expect(screen.getByText("AI board update applied")).toBeInTheDocument();
  });
});
