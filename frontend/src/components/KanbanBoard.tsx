"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { createId, initialData, moveCard, type BoardData } from "@/lib/kanban";
import {
  fetchBoard,
  saveBoard,
  sendChatMessage,
  type ChatHistoryTurn,
} from "@/lib/boardApi";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export const KanbanBoard = () => {
  const [board, setBoard] = useState<BoardData>(() => initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const saveTimeoutRef = useRef<number | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatError, setChatError] = useState<string | null>(null);
  const [isChatLoading, setIsChatLoading] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);

  useEffect(() => {
    let cancelled = false;

    const loadBoard = async () => {
      setIsLoading(true);
      setSaveError(null);
      try {
        const latestBoard = await fetchBoard();
        if (!cancelled) {
          setBoard(latestBoard);
        }
      } catch {
        if (!cancelled) {
          setSaveError("Unable to load the latest board. Showing local fallback data.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadBoard();
    return () => {
      cancelled = true;
      if (saveTimeoutRef.current) {
        window.clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const queueSave = useCallback((nextBoard: BoardData) => {
    setSaveMessage(null);
    if (saveTimeoutRef.current) {
      window.clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = window.setTimeout(async () => {
      setIsSaving(true);
      setSaveError(null);
      try {
        await saveBoard(nextBoard);
        setSaveMessage("Saved");
      } catch {
        setSaveError("Could not save board changes. Please try again.");
      } finally {
        setIsSaving(false);
      }
    }, 250);
  }, []);

  const applyBoardUpdate = useCallback(
    (updater: (prev: BoardData) => BoardData) => {
      setBoard((prev) => {
        const next = updater(prev);
        queueSave(next);
        return next;
      });
    },
    [queueSave]
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    applyBoardUpdate((prev) => ({
      ...prev,
      columns: moveCard(prev.columns, active.id as string, over.id as string),
    }));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    applyBoardUpdate((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    applyBoardUpdate((prev) => ({
      ...prev,
      cards: {
        ...prev.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    }));
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    applyBoardUpdate((prev) => {
      return {
        ...prev,
        cards: Object.fromEntries(
          Object.entries(prev.cards).filter(([id]) => id !== cardId)
        ),
        columns: prev.columns.map((column) =>
          column.id === columnId
            ? {
                ...column,
                cardIds: column.cardIds.filter((id) => id !== cardId),
              }
            : column
        ),
      };
    });
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;
  const canSendChat = chatInput.trim().length > 0 && !isChatLoading;

  const handleSendChat = async () => {
    const prompt = chatInput.trim();
    if (!prompt || isChatLoading) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createId("chat"),
      role: "user",
      content: prompt,
    };
    const nextMessages = [...chatMessages, userMessage];

    setChatMessages(nextMessages);
    setChatInput("");
    setChatError(null);
    setIsChatLoading(true);

    try {
      const history: ChatHistoryTurn[] = chatMessages.map((message) => ({
        role: message.role,
        content: message.content,
      }));
      const result = await sendChatMessage(prompt, history);
      setChatMessages((prev) => [
        ...prev,
        {
          id: createId("chat"),
          role: "assistant",
          content: result.assistantMessage,
        },
      ]);

      if (result.boardUpdate) {
        setBoard(result.boardUpdate);
        setSaveMessage("AI board update applied");
        setSaveError(null);
      }
    } catch (error) {
      setChatError(
        error instanceof Error ? error.message : "Unable to reach AI assistant."
      );
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex flex-col items-end gap-3">
              <a
                href="/logout"
                className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
              >
                Log out
              </a>
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Focus
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.2em]">
            {isLoading ? (
              <span className="text-[var(--gray-text)]">Loading board...</span>
            ) : null}
            {isSaving ? (
              <span className="text-[var(--primary-blue)]">Saving...</span>
            ) : null}
            {!isSaving && saveMessage ? (
              <span className="text-[var(--gray-text)]">{saveMessage}</span>
            ) : null}
            {saveError ? <span className="text-[#b42318]">{saveError}</span> : null}
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds
                    .map((cardId) => board.cards[cardId])
                    .filter((card): card is (typeof board.cards)[string] => Boolean(card))}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          <aside className="flex min-h-[640px] flex-col rounded-[28px] border border-[var(--stroke)] bg-white/85 p-5 shadow-[var(--shadow)] backdrop-blur">
            <div className="border-b border-[var(--stroke)] pb-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                AI assistant
              </p>
              <h2 className="mt-2 font-display text-2xl font-semibold text-[var(--navy-dark)]">
                Board Chat
              </h2>
              <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
                Ask to create, edit, or move cards. Board updates refresh automatically.
              </p>
            </div>

            <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1" data-testid="chat-thread">
              {chatMessages.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-[var(--stroke)] px-4 py-3 text-sm text-[var(--gray-text)]">
                  Start with a request like: move card-1 to Done.
                </p>
              ) : null}
              {chatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                    message.role === "user"
                      ? "ml-6 bg-[var(--primary-blue)] text-white"
                      : "mr-6 border border-[var(--stroke)] bg-[var(--surface)] text-[var(--navy-dark)]"
                  }`}
                >
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] opacity-80">
                    {message.role}
                  </p>
                  <p>{message.content}</p>
                </div>
              ))}
              {isChatLoading ? (
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)]">
                  AI is thinking...
                </p>
              ) : null}
            </div>

            <div className="mt-4 border-t border-[var(--stroke)] pt-4">
              <label
                htmlFor="chat-message"
                className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
              >
                Message
              </label>
              <textarea
                id="chat-message"
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="Ask AI to update your board..."
                className="mt-2 min-h-24 w-full rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--secondary-purple)]"
              />
              {chatError ? (
                <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#b42318]">
                  {chatError}
                </p>
              ) : null}
              <button
                type="button"
                onClick={() => void handleSendChat()}
                disabled={!canSendChat}
                className="mt-3 w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-white transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Send to AI
              </button>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
};
