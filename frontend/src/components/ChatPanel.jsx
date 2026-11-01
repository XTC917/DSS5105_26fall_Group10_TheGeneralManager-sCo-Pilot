import { useEffect, useRef, useState } from "react";
import { confirmAction, declineAction, sendChatStream } from "../services/api.js";
import MessageBubble from "./MessageBubble.jsx";

const CHAR_MS = 28;

const FEATURED_STARTERS = [
  "Which orders are at risk right now?",
  "Give me this morning's briefing",
  "How is ORD-120 doing?",
  "Can we take 800 hoodies by August 25?",
];

const MORE_STARTERS = [
  "How is the TrendCart order doing?",
  "Why is ORD-120 considered risky?",
  "What should I be concerned about right now?",
  "List the TrendCart orders",
  "Tell me if ORD-005 hasn't moved by Thursday",
  "Cancel the watch on ORD-005",
];

function stepLabel(progress) {
  return String(progress || "Checking the question").replace(/[\s.。…]+$/u, "");
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning. What can I help you with?";
  if (hour < 18) return "Good afternoon. What can I help you with?";
  return "Good evening. What can I help you with?";
}

function releasedEnd(chars, official) {
  if (official) return chars.length;
  for (let i = chars.length - 1; i >= 0; i -= 1) {
    if (chars[i] === "\n") return i + 1;
  }
  return 0;
}

function hasUnclosedMark(text) {
  const bold = text.split("**").length - 1;
  const code = text.split("`").length - 1;
  return bold % 2 === 1 || code % 2 === 1;
}

function SparkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}

function ArrowUpIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M6 11l6-6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronIcon({ open }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={`transition-transform duration-[var(--dur-fast)] ${open ? "rotate-180" : ""}`}
    >
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function ChatPanel({
  conversationId,
  llmReady,
  onBoardChanged,
  onBusyChange,
  onConversationUpdated,
  onOpenConversations,
  initialMessages = [],
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(() => initialMessages);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [morePromptsOpen, setMorePromptsOpen] = useState(false);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const listRef = useRef(null);
  const textareaRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const typer = useRef({
    chars: [],
    shown: 0,
    timer: null,
    official: null,
    resolve: null,
  });

  function stopTyper() {
    if (typer.current.timer) {
      clearInterval(typer.current.timer);
      typer.current.timer = null;
    }
  }

  function resetTyper() {
    stopTyper();
    const resolve = typer.current.resolve;
    typer.current = { chars: [], shown: 0, timer: null, official: null, resolve: null };
    resolve?.();
  }

  useEffect(() => resetTyper, []);

  function paintTyped() {
    const content = typer.current.chars.slice(0, typer.current.shown).join("");
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.streaming) {
        const next = [...prev];
        next[next.length - 1] = { ...last, content };
        return next;
      }
      if (!content) return prev;
      return [...prev, { role: "assistant", content, streaming: true }];
    });
  }

  function commitOfficial() {
    const official = typer.current.official;
    const resolve = typer.current.resolve;
    typer.current.official = null;
    typer.current.resolve = null;
    if (official) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.streaming) return [...prev.slice(0, -1), official];
        return [...prev, official];
      });
    }
    resolve?.();
  }

  function tickTyper() {
    const state = typer.current;
    const limit = releasedEnd(state.chars, state.official);
    if (state.shown < limit) {
      state.shown += 1;
      while (
        state.shown < limit &&
        hasUnclosedMark(state.chars.slice(0, state.shown).join(""))
      ) {
        state.shown += 1;
      }
      paintTyped();
      return;
    }
    stopTyper();
    if (state.official) commitOfficial();
  }

  function startTyper() {
    if (!typer.current.timer) typer.current.timer = setInterval(tickTyper, CHAR_MS);
  }

  function queueAnswer(text) {
    typer.current.chars.push(...Array.from(text || ""));
    startTyper();
  }

  function revealOfficial(official) {
    const state = typer.current;
    const target = Array.from(official.content || "");
    const typed = state.chars.join("");
    const full = target.join("");
    if (!full.startsWith(typed)) {
      state.chars = target;
      state.shown = 0;
      paintTyped();
    } else {
      state.chars = target;
    }
    state.official = official;
    if (state.shown >= state.chars.length) {
      stopTyper();
      commitOfficial();
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      state.resolve = resolve;
      startTyper();
    });
  }

  useEffect(() => {
    onBusyChange?.(busy);
    return () => onBusyChange?.(false);
  }, [busy, onBusyChange]);

  function handleScroll() {
    const el = listRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distance < 80;
  }

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (stickToBottomRef.current) {
      requestAnimationFrame(() => {
        el.scrollTo({ top: el.scrollHeight, behavior: busy ? "auto" : "smooth" });
      });
    }
  }, [messages, progress, busy]);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight });
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  function assistantMessage(result) {
    return {
      role: "assistant",
      content: result.answer,
      toolsUsed: result.tools_used || [],
      traces: result.traces || [],
      limitation: result.limitation,
      proposedActions: result.proposed_actions || [],
      charts: result.charts || [],
      tables: result.tables || [],
      clarification: result.clarification || null,
      why: result.why || null,
    };
  }

  async function submit(text, clarificationReply = false, originalQuestion = "") {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    setProgress("");
    setSuggestionsOpen(false);
    const userMsg = { role: "user", content };
    stickToBottomRef.current = true;
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);
    try {
      const result = await sendChatStream(content, conversationId, clarificationReply, originalQuestion, {
        onProgress: setProgress,
        onToken: (token) => {
          if (token?.reset) {
            resetTyper();
            setMessages((prev) => (prev[prev.length - 1]?.streaming ? prev.slice(0, -1) : prev));
            return;
          }
          if (token?.text) queueAnswer(token.text);
        },
      });
      await revealOfficial(assistantMessage(result));
      onConversationUpdated?.();
    } catch (err) {
      resetTyper();
      setMessages((prev) => (prev[prev.length - 1]?.streaming ? prev.slice(0, -1) : prev));
      setError(err.message);
    } finally {
      setBusy(false);
      setProgress("");
      requestAnimationFrame(() => {
        const el = listRef.current;
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      });
    }
  }

  async function confirm(index, action) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await confirmAction(action);
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === index
            ? {
                ...msg,
                proposedActions: [],
                decision: { status: "confirmed", summary: result.summary },
              }
            : msg,
        ),
      );
      onBoardChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function dismiss(index, action) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await declineAction(action);
      setMessages((prev) =>
        prev.map((msg, i) =>
          i === index
            ? { ...msg, proposedActions: [], decision: { status: "dismissed" } }
            : msg,
        ),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function scrollToBottom() {
    const el = listRef.current;
    if (!el) return;
    stickToBottomRef.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }

  function renderComposer({ welcome = false } = {}) {
    return (
      <form
        className={welcome ? "w-full" : "shrink-0 px-3 pb-3 pt-2 md:px-6 md:pb-5"}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div
          className={`composer-shell mx-auto flex w-full flex-col rounded-[26px] border border-line bg-surface shadow-soft transition-[border-color,box-shadow] duration-[var(--dur)] focus-within:border-accentText focus-within:shadow-card ${
            welcome ? "max-w-2xl" : "max-w-4xl"
          }`}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask about orders, risk, or new-order feasibility…"
            className="max-h-40 min-h-[52px] w-full resize-none bg-transparent px-4 pt-4 type-body text-foreground outline-none placeholder:text-subtle"
          />
          <div className="flex items-center justify-between gap-2 px-3 pb-3">
            <div className="flex min-w-0 items-center gap-2 type-caption text-subtle">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
              <span className="truncate">Grounded in factory data</span>
              {!welcome && (
                <button
                  type="button"
                  onClick={() => setSuggestionsOpen((value) => !value)}
                  className="focus-ring ml-1 hidden shrink-0 items-center gap-1 rounded-full px-2 py-0.5 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground sm:inline-flex"
                  aria-expanded={suggestionsOpen}
                >
                  Suggestions
                  <ChevronIcon open={suggestionsOpen} />
                </button>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span className="hidden type-caption text-subtle sm:inline">Enter to send · Shift+Enter new line</span>
              <button
                type="submit"
                disabled={busy || !input.trim()}
                aria-label={busy ? "Sending" : "Send message"}
                className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-accentContrast shadow-xs transition-all duration-[var(--dur-fast)] hover:brightness-110 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-accentContrast/40 border-t-accentContrast" />
                ) : (
                  <ArrowUpIcon />
                )}
              </button>
            </div>
          </div>
        </div>
      </form>
    );
  }

  function renderStarterButtons(items, { compact = false } = {}) {
    return (
      <div className={compact ? "grid gap-2" : "grid gap-2 sm:grid-cols-2"}>
        {items.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => submit(question)}
            className="group flex items-center justify-between gap-3 rounded-2xl border border-line/70 bg-surface/70 px-4 py-3 text-left type-sm text-foreground transition-all duration-[var(--dur-fast)] hover:-translate-y-0.5 hover:border-accentText/50 hover:bg-surface hover:shadow-soft"
          >
            <span>{question}</span>
            <span className="text-muted transition-transform duration-[var(--dur-fast)] group-hover:translate-x-0.5 group-hover:text-accentText">→</span>
          </button>
        ))}
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-transparent">
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-8 md:px-8">
          <div className="w-full max-w-2xl space-y-8">
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-accentSoft text-accentText shadow-xs">
                <SparkIcon />
              </div>
              <div className="space-y-2">
                <p className="type-overline text-accentText">SweaterCo GM Co-Pilot</p>
                <h1 className="type-display text-foreground">{greeting()}</h1>
                <p className="mx-auto max-w-xl type-body text-muted">
                  Ask about orders, production risk, feasibility and today&apos;s priorities. Answers are grounded in factory tools, not the model.
                </p>
              </div>
            </div>

            {renderComposer({ welcome: true })}

            {!llmReady && (
              <p className="mx-auto max-w-2xl rounded-2xl border border-warning/30 bg-warningSoft px-4 py-2 text-center type-caption text-warning">
                Chat needs OPENAI_API_KEY in the project .env. pytest still works without it.
              </p>
            )}

            <div className="space-y-3">
              {renderStarterButtons(FEATURED_STARTERS)}
              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={() => setMorePromptsOpen((value) => !value)}
                  className="focus-ring inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground"
                  aria-expanded={morePromptsOpen}
                >
                  {morePromptsOpen ? "Show fewer prompts" : "More prompts"}
                  <ChevronIcon open={morePromptsOpen} />
                </button>
              </div>
              {morePromptsOpen && (
                <div className="animate-fade-in">
                  {renderStarterButtons(MORE_STARTERS, { compact: true })}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-transparent">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-line/60 px-4 py-2 md:px-6">
        <div className="flex min-w-0 items-center gap-2 type-caption text-muted">
          {onOpenConversations && (
            <button
              type="button"
              onClick={onOpenConversations}
              className="focus-ring inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-1 type-caption font-medium text-foreground transition-colors hover:bg-surfaceMuted md:hidden"
            >
              Chats
            </button>
          )}
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
          <span className="truncate">Grounded factory answers</span>
          {busy && <span className="working-step text-subtle">· working</span>}
        </div>
        <button
          type="button"
          onClick={() => setSuggestionsOpen((value) => !value)}
          className="focus-ring hidden items-center gap-1 rounded-full px-2 py-1 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground sm:inline-flex"
          aria-expanded={suggestionsOpen}
        >
          Suggestions
          <ChevronIcon open={suggestionsOpen} />
        </button>
      </div>

      <div className="relative min-h-0 flex-1">
        <div
          ref={listRef}
          onScroll={handleScroll}
          className="h-full min-w-0 overflow-x-hidden overflow-y-auto overscroll-contain px-4 py-5 md:px-6"
        >
          <div className="mx-auto w-full max-w-4xl space-y-7">
            {messages.map((msg, idx) => (
              <MessageBubble
                key={`${msg.role}-${idx}`}
                message={msg}
                busy={busy}
                onConfirm={(action) => confirm(idx, action)}
                onDismiss={(action) => dismiss(idx, action)}
                onClarify={(text) => {
                  const original = [...messages].reverse().find((item) => item.role === "user")?.content || "";
                  setMessages((prev) =>
                    prev.map((item, i) => (i === idx ? { ...item, clarification: null } : item)),
                  );
                  submit(text, true, original);
                }}
                clarificationOpen={idx === messages.length - 1}
              />
            ))}
            {busy && !(messages.at(-1)?.streaming && messages.at(-1)?.content) && (
              <div className="flex items-center gap-2 type-caption text-muted" role="status" aria-live="polite">
                <span className="stream-dot h-1.5 w-1.5 rounded-full bg-accent" />
                <span className="working-step">{stepLabel(progress)}…</span>
              </div>
            )}
          </div>
        </div>

        {!isAtBottom && messages.length > 0 && (
          <button
            type="button"
            onClick={scrollToBottom}
            className="focus-ring absolute bottom-4 right-4 rounded-full border border-line bg-surface px-3 py-1.5 type-caption font-medium text-foreground shadow-soft transition-colors hover:bg-surfaceMuted"
          >
            ↓ Latest
          </button>
        )}
      </div>

      {suggestionsOpen && (
        <div className="shrink-0 border-t border-line/60 bg-surface/70 px-4 py-3 md:px-6">
          <div className="mx-auto w-full max-w-4xl space-y-2">
            <p className="type-overline text-muted">Suggested prompts</p>
            <div className="flex max-h-28 flex-wrap gap-2 overflow-y-auto">
              {[...FEATURED_STARTERS, ...MORE_STARTERS].map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => submit(question)}
                  className="rounded-full border border-line bg-surfaceMuted px-3 py-1 type-caption text-foreground transition-colors hover:border-accentText hover:bg-accentSoft/40"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mx-3 mb-2 flex items-start justify-between gap-3 rounded-2xl border border-danger/30 bg-dangerSoft px-4 py-2.5 type-caption text-danger md:mx-6">
          <span className="min-w-0 break-words">{error}</span>
          <button
            type="button"
            onClick={() => setError("")}
            className="focus-ring shrink-0 rounded-full px-2 py-0.5 font-medium text-danger/80 hover:text-danger"
          >
            Dismiss
          </button>
        </div>
      )}
      {!llmReady && !error && (
        <p className="mx-3 mb-2 rounded-2xl border border-warning/30 bg-warningSoft px-4 py-2.5 type-caption text-warning md:mx-6">
          Chat needs OPENAI_API_KEY in the project .env. pytest still works without it.
        </p>
      )}

      {renderComposer()}
    </section>
  );
}
