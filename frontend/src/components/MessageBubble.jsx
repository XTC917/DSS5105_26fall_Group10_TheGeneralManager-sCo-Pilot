import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import RichResponseRenderer from "./rich/RichResponseRenderer.jsx";
import TracePanel from "./TracePanel.jsx";
import { useState } from "react";

export default function MessageBubble({ message, onConfirm, onDismiss, busy }) {
  const isUser = message.role === "user";
  const [open, setOpen] = useState(false);
  const traces = message.traces || [];
  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${isUser ? "bg-ink text-paper" : "bg-paper text-ink"}`}>
        {isUser ? <p className="whitespace-pre-wrap">{message.content}</p> : (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || ""}</ReactMarkdown>
          </div>
        )}
        {!isUser && message.presentations?.length > 0 && <RichResponseRenderer presentations={message.presentations} />}
        {!isUser && message.toolsUsed?.length > 0 && (
          <p className="mt-2 text-[11px] uppercase tracking-wide text-ink/45">Tools: {message.toolsUsed.join(" → ")}</p>
        )}
        {!isUser && (message.proposedActions || []).length > 0 && !message.decision && (
          <div className="mt-2 space-y-2 rounded border border-ink/10 bg-white px-2 py-2">
            {(message.proposedActions || []).map((item, idx) => (
              <div key={idx} className="flex gap-2">
                <button type="button" disabled={busy} onClick={() => onConfirm?.(item)} className="rounded bg-ink px-3 py-1 text-xs text-paper">Confirm</button>
                <button type="button" disabled={busy} onClick={() => onDismiss?.(item)} className="rounded border px-3 py-1 text-xs">Dismiss</button>
              </div>
            ))}
          </div>
        )}
        {!isUser && traces.length > 0 && (
          <div className="mt-2">
            <button type="button" onClick={() => setOpen((v) => !v)} className="text-xs font-medium underline decoration-brass underline-offset-2">
              {open ? "Hide evidence" : "Why? Show source rows"}
            </button>
            {open && <TracePanel traces={traces} />}
          </div>
        )}
      </div>
    </article>
  );
}
