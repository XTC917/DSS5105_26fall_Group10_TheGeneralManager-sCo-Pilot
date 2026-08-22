import { useState } from "react";
import TracePanel from "./TracePanel.jsx";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const [open, setOpen] = useState(false);
  const traces = message.traces || [];

  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser ? "bg-ink text-paper" : "bg-paper text-ink"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {!isUser && message.toolsUsed?.length > 0 && (
          <p className="mt-2 text-[11px] uppercase tracking-wide text-ink/45">
            Tools: {message.toolsUsed.join(" → ")}
          </p>
        )}
        {!isUser && traces.length > 0 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="text-xs font-medium text-ink underline decoration-brass underline-offset-2"
            >
              {open ? "Hide evidence" : "Why? Show source rows"}
            </button>
            {open && <TracePanel traces={traces} />}
          </div>
        )}
      </div>
    </article>
  );
}
