import { useEffect, useRef, useState } from "react";
import { confirmAction, declineAction, sendChatStream } from "../services/api.js";
import MessageBubble from "./MessageBubble.jsx";

const CHAR_MS = 28;

const STARTERS = [
  "How is ORD-120 doing?",
  "How is the TrendCart order doing?",
  "Which orders are at risk?",
  "Why is ORD-120 considered risky?",
  "Can we take 800 hoodies by August 25?",
  "Give me this morning's briefing",
  "What should I be concerned about right now?",
  "List the TrendCart orders",
  "Tell me if ORD-005 hasn't moved by Thursday",
  "Cancel the watch on ORD-005",
];

function stepLabel(progress) {
  return String(progress || "Checking the question").replace(/[\s.。…]+$/u, "");
}

function WorkingDots() {
  return (
    <span className="working-dots" aria-hidden="true">
      <span>.</span>
      <span>.</span>
      <span>.</span>
    </span>
  );
}

export default function ChatPanel({
  conversationId,
  llmReady,
  onBoardChanged,
  onBusyChange,
  onConversationUpdated,
  initialMessages = [],
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(() => initialMessages);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const listRef = useRef(null);
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
    if (state.shown < state.chars.length) {
      state.shown += 1;
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

  useEffect(() => {
    if (!busy) return;
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, progress, busy]);

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
    const userMsg = { role: "user", content };
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
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
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

  return (
    <section className="flex min-h-[70vh] min-w-0 flex-col rounded-lg border border-ink/10 bg-white shadow-sm">
      <div className="border-b border-ink/10 px-4 py-3">
        <h2 className="text-sm font-semibold">Ask about factory operations</h2>
        <p className="text-xs text-ink/55">
          Answers are grounded in orders, production_log, and workshops. Numbers come from
          tools, not from the model.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-ink/5 px-4 py-3">
        {STARTERS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => submit(q)}
            className="rounded-full border border-ink/15 px-3 py-1 text-left text-xs text-ink/80 hover:border-brass hover:bg-paper"
          >
            {q}
          </button>
        ))}
      </div>

      <div ref={listRef} className="min-w-0 flex-1 space-y-3 overflow-x-hidden overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="text-sm text-ink/45">
            Try a starter above, or ask for a specific order id such as ORD-120.
          </p>
        )}
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
          <p className="text-xs text-ink/45">
            {stepLabel(progress)}
            <WorkingDots />
          </p>
        )}
      </div>

      {error && (
        <p className="mx-4 mb-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
          {error}
        </p>
      )}
      {!llmReady && !error && (
        <p className="mx-4 mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Chat needs OPENAI_API_KEY in the project .env. pytest still works without it.
        </p>
      )}

      <form
        className="flex gap-2 border-t border-ink/10 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about an order, risk, or a new-order feasibility…"
          className="flex-1 rounded border border-ink/15 px-3 py-2 text-sm outline-none focus:border-brass"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-ink px-4 py-2 text-sm font-medium text-paper disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </section>
  );
}
