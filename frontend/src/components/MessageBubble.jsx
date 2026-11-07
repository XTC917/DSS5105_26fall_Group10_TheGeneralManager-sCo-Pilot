import { useState } from "react";
import ChartView from "./ChartView.jsx";
import TableView from "./TableView.jsx";
import TracePanel from "./TracePanel.jsx";
import EmailDraft from "./EmailDraft.jsx";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function actionLabel(action) {
  const type = action?.type;
  const order = action?.order_id || "";
  if (type === "create_watch") {
    return `Save watch on ${order}${action.check_date ? ` by ${action.check_date}` : ""}`;
  }
  if (type === "cancel_watch") {
    return `Cancel the watch on ${order}`;
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

function stripEmbeddedImages(text) {
  return String(text || "")
    .replace(/!\[[^\]]*]\(\s*data:image\/[^)]*\)/g, "")
    .replace(/\[[^\]]*]\(\s*data:image\/[^)]*\)/g, "")
    .replace(/data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function SparkIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
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

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}

function answerPlainText(markdown, tables) {
  const prose = String(markdown || "")
    .replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, (_, code) => code.trim())
    .replace(/!\[[^\]]*]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^>\s?/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  const tableBlocks = (tables || []).map((table) => {
    const columns = Array.isArray(table?.columns) ? table.columns : [];
    const rows = Array.isArray(table?.rows) ? table.rows : [];
    if (!columns.length || !rows.length) return "";
    const header = columns.map((column) => column.label || column.key).join("\t");
    const lines = rows.map((row) => columns.map((column) => (row?.[column.key] == null ? "" : String(row[column.key]))).join("\t"));
    return [table.title, header, ...lines].filter(Boolean).join("\n");
  }).filter(Boolean);
  return [prose, ...tableBlocks].filter(Boolean).join("\n\n");
}

async function writeClipboard(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const area = document.createElement("textarea");
  area.value = value;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.left = "-9999px";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}

function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false);
  if (!text) return null;
  return (
    <button
      type="button"
      aria-label={copied ? "Copied" : label}
      title={copied ? "Copied" : label}
      onClick={async () => {
        try {
          await writeClipboard(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          setCopied(false);
        }
      }}
      className="focus-ring inline-flex items-center gap-1.5 rounded-full px-2 py-1 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground"
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
    </button>
  );
}

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function limitationLabel(limitation) {
  if (!limitation) return "";
  if (typeof limitation === "string") return limitation;
  return limitation.message || limitation.reason || "Limited data for this answer";
}

function MessageMeta({ message }) {
  const label = limitationLabel(message.limitation);
  if (!label || /^[a-z][a-z0-9_]*$/.test(label)) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      <span className="inline-flex max-w-full items-center rounded-full border border-warning/30 bg-warningSoft px-2.5 py-0.5 type-caption text-warning">
        <span className="truncate">{label}</span>
      </span>
    </div>
  );
}

function clarificationReplyText(prompt, answer) {
  const question = String(prompt || "").trim();
  const chosen = String(answer || "").trim();
  if (!question || question === chosen) return chosen;
  return `${question}\n${chosen}`;
}

function choiceLines(choice) {
  return String(choice || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function optionWasChosen(option, choice) {
  const lines = choiceLines(choice);
  const label = String(option?.label || "").trim();
  const message = String(option?.message || "").trim();
  return Boolean(
    (label && (choice === label || lines.includes(label))) ||
      (message && (choice === message || lines.includes(message))),
  );
}

function FrozenOptions({ options, choice }) {
  return (
    <div className="grid gap-2">
      {(options || []).map((option, index) => {
        const chosen = optionWasChosen(option, choice);
        return (
          <div
            key={`${option.label}-${index}`}
            className={`rounded-xl border px-3.5 py-2.5 text-left type-sm ${
              chosen
                ? "border-accent bg-accent font-semibold text-accentContrast"
                : "border-line bg-surfaceMuted text-muted"
            }`}
          >
            {option.label}
          </div>
        );
      })}
    </div>
  );
}

function FrozenClarification({ clarification, choice }) {
  const questions = clarification.questions || [];
  return (
    <div className="space-y-4 rounded-2xl border border-line bg-surfaceMuted/40 p-4">
      {clarification.prompt && <p className="type-sm text-muted">{clarification.prompt}</p>}
      {questions.length > 0 ? (
        questions.map((question) => (
          <div key={question.id} className="space-y-2">
            {question.prompt && question.prompt !== clarification.prompt && (
              <p className="type-sm font-medium text-foreground">{question.prompt}</p>
            )}
            <FrozenOptions options={question.options} choice={choice} />
          </div>
        ))
      ) : (
        <FrozenOptions options={clarification.options} choice={choice} />
      )}
    </div>
  );
}

function ClarificationCard({ clarification, busy, onClarify }) {
  const questions = clarification.questions;
  const [picked, setPicked] = useState({});
  const [other, setOther] = useState({});
  const ready = questions.every((question) => {
    const custom = (other[question.id] || "").trim();
    return Boolean(picked[question.id] || custom);
  });

  function submit(event) {
    event.preventDefault();
    if (!ready) return;
    const lines = questions.map((question) => {
      const custom = (other[question.id] || "").trim();
      const chosen = picked[question.id];
      return clarificationReplyText(question.prompt, custom || chosen?.label || "");
    });
    onClarify?.(lines.join("\n\n"));
  }

  return (
    <div className="rounded-2xl border border-line bg-surfaceMuted/40 p-4">
      <form className="space-y-4" onSubmit={submit}>
        {questions.length > 1 && clarification.prompt && (
          <p className="type-sm text-muted">{clarification.prompt}</p>
        )}
        {questions.map((question) => (
          <fieldset key={question.id} className="space-y-2">
            {question.prompt !== clarification.prompt && (
              <legend className="mb-1 type-sm font-medium text-foreground">{question.prompt}</legend>
            )}
            <div className="grid gap-2">
              {question.options.map((option, index) => {
                const selected =
                  picked[question.id]?.label === option.label &&
                  !(other[question.id] || "").trim();
                return (
                  <button
                    key={`${option.label}-${index}`}
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setPicked((current) => ({ ...current, [question.id]: option }));
                      setOther((current) => ({ ...current, [question.id]: "" }));
                    }}
                    className={`rounded-xl border px-3.5 py-2.5 text-left type-sm text-foreground transition-colors disabled:opacity-50 ${
                      selected
                        ? "border-accent bg-accentSoft/60"
                        : "border-line bg-surface hover:border-accentText/60 hover:bg-surfaceMuted"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <input
              value={other[question.id] || ""}
              onChange={(event) =>
                setOther((current) => ({ ...current, [question.id]: event.target.value }))
              }
              disabled={busy}
              placeholder={clarification.other_placeholder || "Other"}
              className="w-full rounded-xl border border-line bg-surface px-3 py-2 type-sm text-foreground outline-none transition-colors placeholder:text-subtle focus:border-accentText"
            />
          </fieldset>
        ))}
        <button
          type="submit"
          disabled={busy || !ready}
          className="rounded-full bg-accent px-4 py-2 type-caption font-semibold text-accentContrast transition-opacity hover:brightness-110 disabled:opacity-40"
        >
          {clarification.other_submit || "Send"}
        </button>
      </form>
    </div>
  );
}

export default function MessageBubble({
  message,
  onConfirm,
  onDismiss,
  onClarify,
  busy,
  clarificationOpen = false,
  actionOffer = null,
  actionOfferDecision = null,
  onAcceptOffer,
  onDeclineOffer,
}) {
  const isUser = message.role === "user";
  const [open, setOpen] = useState(false);
  const [other, setOther] = useState("");
  const traces = message.traces || [];
  const proposed = message.proposedActions || [];
  const charts = message.charts || [];
  const tables = message.tables || [];
  const clarification = message.clarification;
  const decision = message.decision;

  const content = isUser ? message.content : stripEmbeddedImages(message.content);
  const copyText = isUser ? "" : answerPlainText(content, message.tables || []);

  if (isUser) {
    return (
      <article className="message-enter flex justify-end">
        <div className="flex max-w-[min(85%,42rem)] flex-col items-end gap-1">
          <div className="select-text rounded-2xl bg-accentSoft px-4 py-2.5 type-sm leading-relaxed text-foreground shadow-xs">
            <p className="question-text cursor-text select-text whitespace-pre-wrap break-words">{message.content}</p>
          </div>
          <CopyButton text={String(message.content || "").trim()} label="Copy question" />
        </div>
      </article>
    );
  }

  return (
    <article className="message-enter flex w-full min-w-0 flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accentSoft text-accentText">
          <SparkIcon />
        </span>
        <span className="type-caption font-semibold text-foreground">Co-Pilot</span>
        {message.streaming && (
          <span className="working-step type-caption text-subtle">writing…</span>
        )}
      </div>

      <div className="w-full min-w-0 space-y-3">
        <div className="w-full min-w-0 space-y-3 break-words text-[0.9375rem] leading-7 text-foreground [overflow-wrap:anywhere] [&_a]:text-accentText [&_a]:underline [&_a]:underline-offset-2 [&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-accent [&_blockquote]:pl-4 [&_blockquote]:text-muted [&_code]:rounded [&_code]:bg-surfaceMuted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.85em] [&_h1]:mt-5 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mt-5 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mt-4 [&_h3]:text-base [&_h3]:font-semibold [&_li]:my-1 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-0 [&_p+p]:mt-3 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:bg-surfaceMuted [&_pre]:p-4 [&_pre]:text-sm [&_table]:my-3 [&_table]:w-full [&_table]:min-w-0 [&_table]:border-collapse [&_td]:border [&_td]:border-line/30 [&_td]:px-3 [&_td]:py-2 [&_th]:border [&_th]:border-line/30 [&_th]:bg-surfaceMuted [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_.overflow-x-auto]:max-w-full">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              img: () => null,
              a: ({ href, children }) =>
                String(href || "").startsWith("data:image") ? null : <a href={href}>{children}</a>,
            }}
          >
            {content}
          </ReactMarkdown>
          {message.streaming && content && (
            <span className="ml-0.5 inline-block h-4 w-1 animate-pulse rounded-full bg-accentText align-middle" />
          )}
        </div>

        {message.turnId && message.emailDrafts?.map((draft, index) => (
          <EmailDraft key={`${message.turnId}-${index}`} draft={draft}
            turnId={message.turnId} index={index} locked={!clarificationOpen} />
        ))}
        <MessageMeta message={message} />

        {charts.map((chart, idx) => (
          <div key={`${chart.type || "chart"}-${idx}`} className="w-full min-w-0">
            <ChartView chart={chart} />
          </div>
        ))}

        {tables.map((table, idx) => (
          <div key={`${table.title}-${idx}`} className="w-full min-w-0">
            <TableView table={table} />
          </div>
        ))}

        {clarification && (message.clarificationChoice || !clarificationOpen) && (
          <FrozenClarification clarification={clarification} choice={message.clarificationChoice || ""} />
        )}

        {clarificationOpen && !message.clarificationChoice && clarification?.questions?.length > 0 && (
          <ClarificationCard clarification={clarification} busy={busy} onClarify={onClarify} />
        )}

        {clarificationOpen &&
          !message.clarificationChoice &&
          !clarification?.questions?.length &&
          clarification?.options?.length > 0 && (
            <div className="space-y-2 rounded-2xl border border-line bg-surfaceMuted/40 p-4">
              <div className="grid gap-2">
                {clarification.options.map((option, index) => (
                  <button
                    key={`${option.label}-${index}`}
                    type="button"
                    disabled={busy}
                    onClick={() => onClarify?.(clarificationReplyText(clarification.prompt, option.label))}
                    className="rounded-xl border border-line bg-surface px-3.5 py-2.5 text-left type-sm text-foreground transition-colors hover:border-accentText/60 hover:bg-surfaceMuted disabled:opacity-50"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <form
                className="flex gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  const text = other.trim();
                  if (!text) return;
                  setOther("");
                  onClarify?.(clarificationReplyText(clarification.prompt, text));
                }}
              >
                <input
                  value={other}
                  onChange={(event) => setOther(event.target.value)}
                  disabled={busy}
                  placeholder={clarification.other_placeholder || "Other"}
                  className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-3 py-2 type-sm text-foreground outline-none transition-colors placeholder:text-subtle focus:border-accentText"
                />
                <button
                  type="submit"
                  disabled={busy || !other.trim()}
                  className="rounded-full bg-accent px-4 py-2 type-caption font-semibold text-accentContrast transition-opacity hover:brightness-110 disabled:opacity-40"
                >
                  {clarification.other_submit || "Send"}
                </button>
              </form>
            </div>
          )}

        {proposed.length > 0 && !decision && (
          <div className="rounded-2xl border border-line bg-surfaceMuted/40 p-3.5">
            <p className="type-caption text-muted">
              Proposed action · needs confirmation. Email is never actually sent.
            </p>
            <div className="mt-2 space-y-2">
              {proposed.map((item, idx) => (
                <div
                  key={`${item.type}-${idx}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line/70 bg-surface px-3 py-2.5"
                >
                  <span className="min-w-0 type-sm text-foreground">{actionLabel(item)}</span>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <button
                      type="button"
                      disabled={busy || !clarificationOpen}
                      onClick={() => onConfirm?.(item)}
                      className="rounded-full bg-accent px-3 py-1.5 type-caption font-semibold text-accentContrast transition-opacity hover:brightness-110 disabled:opacity-40"
                    >
                      Confirm
                    </button>
                    <button
                      type="button"
                      disabled={busy || !clarificationOpen}
                      onClick={() => onDismiss?.(item)}
                      className="rounded-full border border-line px-3 py-1.5 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground disabled:opacity-40"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {decision?.status === "confirmed" && (
          <p className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-successSoft px-3 py-1 type-caption text-success">
            <CheckIcon />
            {decision.summary || "Saved."}
          </p>
        )}
        {decision?.status === "dismissed" && (
          <p className="type-caption text-muted">Dismissed. Nothing was saved.</p>
        )}

        {actionOffer && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-l-2 border-accent pl-3">
            <p className="min-w-0 flex-1 type-sm leading-6 text-foreground">{actionOffer.prompt}</p>
            {actionOfferDecision?.status === "confirmed" && (
              <p className="type-caption text-success">{actionOfferDecision.summary || "Saved."}</p>
            )}
            {actionOfferDecision?.status === "dismissed" && (
              <p className="type-caption text-muted">Dismissed. Nothing was saved.</p>
            )}
            {!actionOfferDecision && (
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  disabled={busy || !clarificationOpen}
                  onClick={onAcceptOffer}
                  className="rounded-full bg-foreground px-3 py-1 type-caption font-medium text-surface transition-opacity hover:opacity-80 disabled:opacity-40"
                >
                  Yes
                </button>
                <button
                  type="button"
                  disabled={busy || !clarificationOpen}
                  onClick={onDeclineOffer}
                  className="rounded-full px-2.5 py-1 type-caption text-muted transition-colors hover:text-foreground disabled:opacity-40"
                >
                  No
                </button>
              </div>
            )}
          </div>
        )}

        {(message.why || traces.length > 0) && (
          <div className="pt-0.5">
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpen((value) => !value)}
              className="focus-ring inline-flex items-center gap-1.5 rounded-full px-2 py-1 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground"
            >
              {open ? "Hide explanation" : "Why this answer?"}
              <ChevronIcon open={open} />
            </button>
            {open && (
              <div className="mt-2 rounded-2xl border border-line bg-surfaceMuted/40 p-3">
                <TracePanel traces={traces} why={message.why} />
              </div>
            )}
          </div>
        )}

        {!message.streaming && <div className="flex justify-start"><CopyButton text={copyText} label="Copy answer" /></div>}
      </div>
    </article>
  );
}
