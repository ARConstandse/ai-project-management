import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];
const mockFetch = vi.fn();

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
    mockFetch.mockResolvedValue(mockFetchResponse(initialData));
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
});
