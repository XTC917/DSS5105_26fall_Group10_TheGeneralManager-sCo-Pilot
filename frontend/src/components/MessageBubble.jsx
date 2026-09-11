import { useState } from "react";
import TracePanel from "./TracePanel.jsx";

function actionLabel(action) {
  const type = action?.type;
  const order = action?.order_id || "";
  if (type === "create_watch") {
    return `Save watch on ${order}${action.check_date ? ` by ${action.check_date}` : ""}`;
  }
  if (type === "cancel_watch") {
    return `Cancel watch${action.watch_id ? ` ${action.watch_id}` : ""} on ${order}`;
  }
  if (type === "create_reminder") {
    return `Save reminder on ${order}`;
  }
  if (type === "add_order_note") {
    return `Save note on ${order}`;
  }
  if (type === "send_email") {
    return `Record simulated send for ${order} (not emailed)`;
  }
  return "Confirm this action";
}

export default function MessageBubble({ message, onConfirm, onDismiss, busy }) {
  const isUser = message.role === "user";
  const [open, setOpen] = useState(false);
  const traces = message.traces || [];
  const proposed = message.proposedActions || [];
  const decision = message.decision;

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
        {!isUser && proposed.length > 0 && !decision && (
          <div className="mt-2 space-y-2 rounded border border-ink/10 bg-white px-2 py-2">
            <p className="text-xs text-ink/70">
              Proposed locally. Click Confirm to save — that is the confirmation step.
              Email is never actually sent.
            </p>
            {proposed.map((item, idx) => (
              <div key={`${item.type}-${idx}`} className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink/80">{actionLabel(item)}</span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onConfirm?.(item)}
                  className="rounded bg-ink px-3 py-1 text-xs font-medium text-paper disabled:opacity-50"
                >
                  Confirm
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onDismiss?.(item)}
                  className="rounded border border-ink/20 px-3 py-1 text-xs text-ink/80 disabled:opacity-50"
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        )}
        {!isUser && decision?.status === "confirmed" && (
          <p className="mt-2 text-xs text-ink/70">{decision.summary}</p>
        )}
        {!isUser && decision?.status === "dismissed" && (
          <p className="mt-2 text-xs text-ink/55">Dismissed. Nothing was saved.</p>
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
