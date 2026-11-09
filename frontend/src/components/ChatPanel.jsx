import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { confirmAction, declineAction, fetchActionOffer, fetchSuggestions, saveActionOffer, sendChatStream } from "../services/api.js";
import MessageBubble from "./MessageBubble.jsx";
import { AiOrb, Icon } from "../pages/design-preview/bits.jsx";

const CHAR_MS = 14;

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
  if (hour < 12) return "Good morning.";
  if (hour < 18) return "Good afternoon.";
  return "Good evening.";
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

export default function ChatPanel({
  conversationId,
  llmReady,
  onBoardChanged,
  onBoardPending,
  onBoardFailed,
  onBoardSaved,
  onBusyChange,
  onConversationUpdated,
  onQuestionSubmitted,
  onQuestionFailed,
  onOpenConversations,
  onNewConversation,
  onDraftChange,
  active = true,
  notice = "",
  onDismissNotice,
  initialMessages = [],
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(() => initialMessages);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [followups, setFollowups] = useState([]);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [suggestionsPos, setSuggestionsPos] = useState(null);
  const listRef = useRef(null);
  const suggestSeq = useRef(0);
  const textareaRef = useRef(null);
  const suggestionsRef = useRef(null);
  const suggestionsPopoverRef = useRef(null);
  const abortRef = useRef(null);
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

  async function loadFollowups(query, asked) {
    const seq = ++suggestSeq.current;
    try {
      const data = await fetchSuggestions({ query, asked, focus: "" });
      const suggestions = Array.isArray(data.suggestions) ? data.suggestions.slice(0, 3) : [];
      return { seq, suggestions };
    } catch {
      return { seq, suggestions: [] };
    }
  }

  useEffect(() => {
    const users = (initialMessages || []).filter((item) => item.role === "user").map((item) => item.content);
    const lastUser = users.at(-1);
    const lastAssistant = [...(initialMessages || [])].reverse().find((item) => item.role === "assistant");
    if (!lastUser || !lastAssistant || lastAssistant.clarification) return undefined;
    let active = true;
    loadFollowups(lastUser, users).then((pending) => {
      if (active && pending.seq === suggestSeq.current) setFollowups(pending.suggestions);
    });
    return () => {
      active = false;
    };
  }, []);

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

  function startTyper(interval = CHAR_MS) {
    if (typer.current.timer && typer.current.interval === interval) return;
    stopTyper();
    typer.current.interval = interval;
    typer.current.timer = setInterval(tickTyper, interval);
  }

  function queueAnswer(text) {
    typer.current.chars.push(...Array.from(text || ""));
    startTyper();
  }

  function revealOfficial(official, interval = CHAR_MS) {
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
      startTyper(interval);
    });
  }

  useEffect(() => {
    onBusyChange?.(conversationId, busy);
    return () => onBusyChange?.(conversationId, false);
  }, [busy, conversationId, onBusyChange]);

  useEffect(() => {
    if (!active) return;
    onDraftChange?.(input);
  }, [active, input, onDraftChange]);

  useLayoutEffect(() => {
    if (!suggestionsOpen) {
      setSuggestionsPos(null);
      return undefined;
    }
    function syncPosition() {
      const anchor = suggestionsRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(22 * 16, Math.max(16 * 16, window.innerWidth - 16));
      const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
      const spaceAbove = rect.top - 8;
      const maxHeight = Math.min(16 * 16, Math.max(10 * 16, spaceAbove));
      setSuggestionsPos({
        left,
        width,
        maxHeight,
        bottom: window.innerHeight - rect.top + 8,
      });
    }
    syncPosition();
    window.addEventListener("resize", syncPosition);
    window.addEventListener("scroll", syncPosition, true);
    return () => {
      window.removeEventListener("resize", syncPosition);
      window.removeEventListener("scroll", syncPosition, true);
    };
  }, [suggestionsOpen]);

  useEffect(() => {
    if (!suggestionsOpen) return undefined;
    function onPointerDown(event) {
      const inButton = suggestionsRef.current?.contains(event.target);
      const inPopover = suggestionsPopoverRef.current?.contains(event.target);
      if (!inButton && !inPopover) setSuggestionsOpen(false);
    }
    function onKeyDown(event) {
      if (event.key === "Escape") setSuggestionsOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [suggestionsOpen]);

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
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input]);

  function assistantMessage(result) {
    return {
      role: "assistant",
      content: result.answer,
      toolsUsed: result.tools_used || [],
      traces: result.traces || [],
      limitation: result.limitation,
      proposedActions: result.proposed_actions || [],
      emailDrafts: result.email_drafts || [],
      turnId: result.turn_id,
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
    suggestSeq.current += 1;
    setFollowups([]);
    const prior = messages.filter((item) => item.role === "user").map((item) => item.content);
    const asked = [...prior, content];
    const userMsg = { role: "user", content };
    stickToBottomRef.current = true;
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);
    onQuestionSubmitted?.(conversationId, content);
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    abortRef.current = controller;
    try {
      const result = await sendChatStream(content, conversationId, clarificationReply, originalQuestion, {
        signal: controller?.signal,
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
      const official = assistantMessage(result);
      const pending = result.clarification ? null : loadFollowups(content, asked);
      const offerPromise = result.clarification
        ? null
        : fetchActionOffer({
            question: content,
            answer: result.answer || "",
            traces: result.traces || [],
            toolsUsed: result.tools_used || [],
            proposedActions: result.proposed_actions || [],
          }).catch(() => null);
      await revealOfficial(official, result.instant ? CHAR_MS / 4 : CHAR_MS);
      onConversationUpdated?.();
      if (pending) {
        const done = await pending;
        if (done.seq === suggestSeq.current) setFollowups(done.suggestions);
      }
      if (offerPromise) {
        const offer = await offerPromise;
        const turnId = official.turnId;
        if (offer?.prompt && offer?.action && turnId) {
          const action = { ...offer.action, _turn_id: turnId };
          await saveActionOffer(turnId, { prompt: offer.prompt, action: offer.action });
          setMessages((prev) =>
            prev.map((msg) =>
              msg.turnId === turnId ? { ...msg, actionOffer: { prompt: offer.prompt, action } } : msg,
            ),
          );
        }
      }
    } catch (err) {
      if (err?.name === "AbortError") {
        // The user stopped receiving. We honestly mark the partial answer as
        // stopped rather than claiming the backend tool run was cancelled.
        resetTyper();
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.streaming) {
            const next = [...prev];
            next[next.length - 1] = { ...last, streaming: false, stopped: true };
            return next;
          }
          return prev;
        });
        setError("Stopped receiving the answer. The server may still finish and save this turn — reload the conversation to see the final answer if it completes.");
      } else {
        resetTyper();
        setMessages((prev) => (prev[prev.length - 1]?.streaming ? prev.slice(0, -1) : prev));
        onQuestionFailed?.(conversationId);
        setError(err.message);
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      setProgress("");
      requestAnimationFrame(() => {
        const el = listRef.current;
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      });
    }
  }

  function stopGenerating() {
    abortRef.current?.abort();
  }

  function rememberOfferDecision(turnId, decision) {
    setMessages((prev) =>
      prev.map((msg) => (msg.turnId === turnId ? { ...msg, actionOfferDecision: decision } : msg)),
    );
  }

  async function acceptOffer(offer) {
    if (!offer?.action || busy) return;
    const savingWatch = offer.action.type === "create_watch";
    setBusy(true);
    setError("");
    if (savingWatch) onBoardPending?.();
    try {
      const result = await confirmAction(offer.action);
      rememberOfferDecision(offer.action._turn_id, {
        status: "confirmed",
        summary: result.summary || "Done.",
      });
      if (savingWatch) onBoardSaved?.();
      else onBoardChanged?.();
    } catch (err) {
      if (savingWatch) onBoardFailed?.();
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function declineOffer(offer) {
    if (!offer?.action || busy) return;
    setBusy(true);
    setError("");
    try {
      await declineAction(offer.action);
      rememberOfferDecision(offer.action._turn_id, {
        status: "dismissed",
        summary: "Dismissed. Nothing was saved.",
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm(index, action) {
    if (busy) return;
    const savingWatch = action?.type === "create_watch";
    setBusy(true);
    setError("");
    if (savingWatch) onBoardPending?.();
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
      if (savingWatch && result?.ok) onBoardSaved?.();
      else if (result?.ok && action?.type === "cancel_watch") onBoardChanged?.();
      else if (savingWatch) onBoardFailed?.();
    } catch (err) {
      if (savingWatch) onBoardFailed?.();
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

  function chooseSuggestion(question) {
    if (input.trim() && !window.confirm("Replace your current draft with this suggestion?")) return;
    setInput(question);
    setSuggestionsOpen(false);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function renderSuggestionsPopover() {
    if (!suggestionsOpen || !suggestionsPos || typeof document === "undefined") return null;
    const prompts = [...FEATURED_STARTERS, ...MORE_STARTERS];
    return createPortal(
      <div
        ref={suggestionsPopoverRef}
        role="dialog"
        aria-label="Suggested prompts"
        className="dp-suggest-pop"
        style={{
          left: suggestionsPos.left,
          bottom: suggestionsPos.bottom,
          width: suggestionsPos.width,
          maxHeight: suggestionsPos.maxHeight,
        }}
      >
        <p className="dp-eyebrow px-2 pb-1.5">Suggested prompts</p>
        <div className="space-y-0.5">
          {prompts.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => chooseSuggestion(question)}
              className="dp-suggest-row focus-ring"
            >
              <Icon name="spark" size={11} className="mt-0.5 shrink-0 text-subtle" />
              <span className="min-w-0 flex-1">{question}</span>
            </button>
          ))}
        </div>
        <p className="mt-1 border-t border-line/60 px-2 pt-1.5 text-[8.5px] text-subtle">
          Fills the composer · never sends automatically
        </p>
      </div>,
      document.body,
    );
  }

  function renderComposer({ welcome = false } = {}) {
    return (
      <form
        className={welcome ? "w-full" : "shrink-0"}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className={`dp-composer relative mx-auto w-full p-2.5 ${welcome ? "max-w-[720px]" : "max-w-[760px]"}`}>
          <div className="flex items-end gap-1.5">
            {welcome && (
              <div ref={suggestionsRef} className="relative shrink-0 self-end">
                <button
                  type="button"
                  aria-label="Suggestions — recommended questions"
                  title="Suggestions — recommended questions"
                  aria-expanded={suggestionsOpen}
                  aria-haspopup="dialog"
                  onClick={() => setSuggestionsOpen((value) => !value)}
                  onMouseEnter={() => {
                    if (typeof window !== "undefined" && window.matchMedia("(hover: hover)").matches) {
                      setSuggestionsOpen(true);
                    }
                  }}
                  className={`dp-suggest-btn focus-ring ${suggestionsOpen ? "is-active" : ""}`}
                >
                  <Icon name="spark" size={13} />
                  <span className="hidden sm:inline">Suggestions</span>
                </button>
                {renderSuggestionsPopover()}
              </div>
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                const desktop = typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;
                if (desktop && e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
              rows={1}
              placeholder={welcome ? "Ask about orders, risk, or feasibility…" : "Ask a follow-up about these orders…"}
              className="dp-composer-input max-h-[120px] min-h-[40px] py-2 text-[13px]"
            />
            {busy ? (
              <button
                type="button"
                onClick={stopGenerating}
                aria-label="Stop generating"
                title="Stop generating — stops receiving. The server may still finish this turn."
                className="dp-send dp-stop focus-ring"
              >
                <Icon name="stop" size={13} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                aria-label="Send message"
                className={`dp-send focus-ring ${!input.trim() ? "is-disabled" : ""}`}
              >
                <Icon name="arrowUp" size={16} strokeWidth={2} />
              </button>
            )}
          </div>
          <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[9px] text-subtle">
            <span className="inline-flex items-center gap-1.5">
              <Icon name="shield" size={10} />
              Grounded in factory data
            </span>
            <span className="hidden items-center gap-1.5 sm:inline-flex">
              <span className="dp-kbd">Enter</span> to send
            </span>
          </div>
        </div>
      </form>
    );
  }

  if (messages.length === 0) {
    return (
      <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-transparent">
        <div className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="dp-welcome min-h-full">
            <div className="dp-hero-grid" aria-hidden="true" />
            <div className="dp-welcome-inner">
              <div className="dp-rise text-center">
                <div className="relative mx-auto mb-7 flex h-[138px] w-[138px] items-center justify-center">
                  <span className="dp-orb-halo" aria-hidden="true" />
                  <AiOrb size={112} />
                  <span className="dp-chip-float left-[-62px] top-4 hidden sm:inline-flex">
                    <Icon name="shield" size={11} />
                    Grounded
                  </span>
                  <span
                    className="dp-chip-float bottom-3 right-[-58px] hidden sm:inline-flex"
                    style={{ animationDelay: "-3s" }}
                  >
                    <Icon name="spark" size={11} />
                    Live tools
                  </span>
                </div>
                <p className="dp-eyebrow text-accentText">SweaterCo · Soft Intelligence</p>
                <h1 className="mt-3 text-[26px] font-semibold leading-[1.08] tracking-[-0.035em] text-foreground sm:text-[34px]">
                  {greeting()}
                  <span className="dp-gradient-ink mt-1 block">What needs your attention?</span>
                </h1>
                <p className="mx-auto mt-4 max-w-[520px] text-[12.5px] leading-6 text-muted sm:text-[13.5px]">
                  Ask about orders, production risk, or feasibility. Every answer is grounded in the
                  factory&apos;s live tools — not the model&apos;s memory.
                </p>
              </div>

              <div className="dp-rise dp-rise-1 mt-8">{renderComposer({ welcome: true })}</div>

              <div className="dp-rise dp-rise-2 mt-4 grid gap-2.5 sm:grid-cols-2">
                {FEATURED_STARTERS.map((question, i) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => chooseSuggestion(question)}
                    className="dp-suggestion focus-ring"
                    title="Fill the composer — does not send"
                  >
                    <span className={`dp-icon-tile dp-tone-${["accent", "warning", "success", "danger"][i % 4]}`}>
                      <Icon name="spark" size={17} />
                    </span>
                    <span className="min-w-0 flex-1 text-left">
                      <span className="block text-[11.5px] font-semibold leading-snug text-foreground">{question}</span>
                      <span className="mt-0.5 block text-[9.5px] text-muted">Tap to fill the composer</span>
                    </span>
                    <Icon name="arrowRight" size={13} className="text-subtle" />
                  </button>
                ))}
              </div>

              {!llmReady && (
                <p className="mx-auto mt-5 max-w-[520px] rounded-2xl border border-warning/30 bg-warningSoft px-4 py-2 text-center type-caption text-warning">
                  Chat needs OPENAI_API_KEY in the project .env. pytest still works without it.
                </p>
              )}
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="dp-chat relative h-full min-h-0">
      {notice ? (
        <div
          role="status"
          className="flex shrink-0 items-start justify-between gap-3 border-b border-warning/25 bg-warningSoft px-4 py-2"
        >
          <p className="type-caption text-warning">{notice}</p>
          {onDismissNotice && (
            <button
              type="button"
              onClick={onDismissNotice}
              className="focus-ring shrink-0 rounded-control px-1.5 type-caption font-medium text-warning"
            >
              Dismiss
            </button>
          )}
        </div>
      ) : null}

      <div ref={listRef} onScroll={handleScroll} className="dp-chat-scroll">
        <div className="mx-auto w-full max-w-4xl space-y-5 md:space-y-7">
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
                  prev.map((item, i) =>
                    i === idx ? { ...item, clarificationChoice: text } : item,
                  ),
                );
                submit(text, true, original);
              }}
              clarificationOpen={idx === messages.length - 1}
              actionOffer={msg.clarification ? null : msg.actionOffer}
              actionOfferDecision={msg.actionOfferDecision}
              onAcceptOffer={() => acceptOffer(msg.actionOffer)}
              onDeclineOffer={() => declineOffer(msg.actionOffer)}
            />
          ))}
          {busy && !(messages.at(-1)?.streaming && messages.at(-1)?.content) && (
            <div className="dp-stream-note" role="status" aria-live="polite">
              <span className="dp-pulse-dot" />
              <span className="working-step">{stepLabel(progress)}…</span>
            </div>
          )}

          {!busy && followups.length > 0 && (
            <div className="dp-go-deeper">
              <div className="dp-go-deeper-head">
                <Icon name="spark" size={11} />
                Go deeper
              </div>
              <div className="dp-go-chips">
                {followups.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => chooseSuggestion(question)}
                    title="Fill the composer with this follow-up"
                    className="dp-go-chip focus-ring"
                  >
                    <span className="dp-go-plus">
                      <Icon name="plus" size={11} />
                    </span>
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {!isAtBottom && messages.length > 0 && (
        <button type="button" onClick={scrollToBottom} className="dp-pill focus-ring absolute bottom-24 right-5 z-10">
          ↓ Latest
        </button>
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

      <div className="dp-chat-composer">{renderComposer()}</div>
    </section>
  );
}
