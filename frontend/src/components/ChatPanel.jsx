import { useRef, useState } from "react";
import { sendChat } from "../services/api.js";
import MessageBubble from "./MessageBubble.jsx";

const STARTERS = [
  "How is ORD-120 doing?",
  "How is the TrendCart order doing?",
  "Which orders are at risk?",
  "Why is ORD-120 considered risky?",
  "Can we take 800 hoodies by August 25?",
];

export default function ChatPanel({ conversationId, llmReady }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef(null);

  async function submit(text) {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    const userMsg = { role: "user", content };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);
    try {
      const result = await sendChat(content, conversationId);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          toolsUsed: result.tools_used || [],
          traces: result.traces || [],
          limitation: result.limitation,
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  }

  return (
    <section className="flex min-h-[70vh] flex-col rounded-lg border border-ink/10 bg-white shadow-sm">
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

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <p className="text-sm text-ink/45">
            Try a starter above, or ask for a specific order id such as ORD-120.
          </p>
        )}
        {messages.map((msg, idx) => (
          <MessageBubble key={`${msg.role}-${idx}`} message={msg} />
        ))}
        {busy && <p className="text-xs text-ink/45">Consulting factory tools…</p>}
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
