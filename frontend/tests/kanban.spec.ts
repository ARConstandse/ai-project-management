import { expect, test, type Page } from "@playwright/test";

type Card = {
  id: string;
  title: string;
  details: string;
};

type Column = {
  id: string;
  title: string;
  cardIds: string[];
};

type BoardData = {
  columns: Column[];
  cards: Record<string, Card>;
};

const seededBoard = (): BoardData => ({
  columns: [
    { id: "col-backlog", title: "Backlog", cardIds: ["card-1", "card-2"] },
    { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
    { id: "col-progress", title: "In Progress", cardIds: ["card-4", "card-5"] },
    { id: "col-review", title: "Review", cardIds: ["card-6"] },
    { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
  ],
  cards: {
    "card-1": {
      id: "card-1",
      title: "Align roadmap themes",
      details: "Draft quarterly themes with impact statements and metrics.",
    },
    "card-2": {
      id: "card-2",
      title: "Gather customer signals",
      details: "Review support tags, sales notes, and churn feedback.",
    },
    "card-3": {
      id: "card-3",
      title: "Prototype analytics view",
      details: "Sketch initial dashboard layout and key drill-downs.",
    },
    "card-4": {
      id: "card-4",
      title: "Refine status language",
      details: "Standardize column labels and tone across the board.",
    },
    "card-5": {
      id: "card-5",
      title: "Design card layout",
      details: "Add hierarchy and spacing for scanning dense lists.",
    },
    "card-6": {
      id: "card-6",
      title: "QA micro-interactions",
      details: "Verify hover, focus, and loading states.",
    },
    "card-7": {
      id: "card-7",
      title: "Ship marketing page",
      details: "Final copy approved and asset pack delivered.",
    },
    "card-8": {
      id: "card-8",
      title: "Close onboarding sprint",
      details: "Document release notes and share internally.",
    },
  },
});

const setupMockBoardApi = async (page: Page) => {
  let board = seededBoard();
  await page.route("**/api/board", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({ status: 200, json: board });
      return;
    }
    if (method === "PUT") {
      board = route.request().postDataJSON() as BoardData;
      await route.fulfill({ status: 200, json: board });
      return;
    }
    await route.fulfill({ status: 405, json: { detail: "Method not allowed" } });
  });
  await page.route("**/api/ai/chat", async (route) => {
    const body = route.request().postDataJSON() as {
      message?: string;
    };
    if ((body.message ?? "").toLowerCase().includes("rename")) {
      board = {
        ...board,
        cards: {
          ...board.cards,
          "card-1": {
            ...board.cards["card-1"],
            title: "AI renamed card",
          },
        },
      };
      await route.fulfill({
        status: 200,
        json: {
          assistantMessage: "Updated card-1 title.",
          boardUpdate: board,
        },
      });
      return;
    }
    await route.fulfill({
      status: 200,
      json: { assistantMessage: "No changes required.", boardUpdate: null },
    });
  });
};

test("loads the kanban board", async ({ page }) => {
  await setupMockBoardApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await setupMockBoardApi(page);
  await page.goto("/");
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await setupMockBoardApi(page);
  await page.goto("/");
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("persists board changes after page refresh", async ({ page }) => {
  await setupMockBoardApi(page);
  await page.goto("/");
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const cardTitle = `Persisted card ${Date.now()}`;

  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill(cardTitle);
  await firstColumn.getByPlaceholder("Details").fill("Survives refresh.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText(cardTitle)).toBeVisible();
  await expect(page.getByText("Saved")).toBeVisible();

  await page.reload();
  const refreshedFirstColumn = page.locator('[data-testid^="column-"]').first();
  await expect(refreshedFirstColumn.getByText(cardTitle)).toBeVisible();
});

test("chat prompt returns reply and applies board update", async ({ page }) => {
  await setupMockBoardApi(page);
  await page.goto("/");

  await page.getByLabel("Message").fill("Rename card 1 title");
  await page.getByRole("button", { name: /send to ai/i }).click();

  await expect(page.getByText("Updated card-1 title.")).toBeVisible();
  await expect(page.getByText("AI renamed card")).toBeVisible();
  await expect(page.getByText("AI board update applied")).toBeVisible();
});
