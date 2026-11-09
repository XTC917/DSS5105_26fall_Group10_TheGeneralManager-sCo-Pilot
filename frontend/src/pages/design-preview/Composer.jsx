import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./bits.jsx";
import { COMPOSER_SUGGESTIONS } from "./mockData.js";

/**
 * Interactive preview composer.
 *
 * - Suggestions live in a portal popover so they are never clipped by a
 *   scroll container. Clicking a suggestion only fills the field (never sends).
 * - While `busy`, the send button becomes a square Stop control.
 * - A non-empty draft is protected: replacing it asks for confirmation first.
 */
export default function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  busy = false,
  compact = false,
  placeholder = "Ask about orders, risk, or feasibility…",
  suggestions = COMPOSER_SUGGESTIONS,
  focusSignal = 0,
  showSuggestions = true,
  className = "",
  listboxLabel = "Suggested prompts",
}) {
  const inputRef = useRef(null);
  const buttonRef = useRef(null);
  const popRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(null);

  useEffect(() => {
    if (!focusSignal) return;
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    const end = el.value.length;
    el.setSelectionRange?.(end, end);
  }, [focusSignal]);

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return undefined;
    }
    function sync() {
      const anchor = buttonRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(22 * 16, Math.max(16 * 16, window.innerWidth - 16));
      const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
      const above = rect.top - 8;
      const maxHeight = Math.min(17 * 16, Math.max(10 * 16, above));
      setPos({ left, width, bottom: window.innerHeight - rect.top + 8, maxHeight });
    }
    sync();
    window.addEventListener("resize", sync);
    window.addEventListener("scroll", sync, true);
    return () => {
      window.removeEventListener("resize", sync);
      window.removeEventListener("scroll", sync, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    function onDown(event) {
      if (buttonRef.current?.contains(event.target)) return;
      if (popRef.current?.contains(event.target)) return;
      setOpen(false);
    }
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function fill(text) {
    if (value.trim() && value.trim() !== text) {
      if (!window.confirm("Replace your current draft with this suggestion?")) return;
    }
    onChange(text);
    setOpen(false);
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      const end = text.length;
      inputRef.current?.setSelectionRange?.(end, end);
    });
  }

  const canSend = value.trim().length > 0 && !busy;

  return (
    <form
      className={`dp-composer ${compact ? "p-1.5" : "p-2.5"} ${className}`}
      onSubmit={(event) => {
        event.preventDefault();
        if (busy) return;
        if (canSend) onSubmit?.();
      }}
    >
      <div className="flex items-end gap-1.5">
        {showSuggestions && (
          <div className="relative shrink-0 self-end">
            <button
              ref={buttonRef}
              type="button"
              aria-label="Suggestions — recommended questions"
              aria-expanded={open}
              aria-haspopup="dialog"
              onClick={() => setOpen((v) => !v)}
              onMouseEnter={() => {
                if (typeof window !== "undefined" && window.matchMedia("(hover: hover)").matches) {
                  setOpen(true);
                }
              }}
              className={`dp-suggest-btn focus-ring ${open ? "is-active" : ""} ${
                compact ? "h-8 w-8 justify-center" : ""
              }`}
            >
              <Icon name="spark" size={compact ? 14 : 13} />
              {!compact && <span className="hidden sm:inline">Suggestions</span>}
            </button>
            {open && pos && typeof document !== "undefined"
              ? createPortal(
                  <div
                    ref={popRef}
                    role="dialog"
                    aria-label={listboxLabel}
                    className="dp-suggest-pop"
                    style={{
                      left: pos.left,
                      bottom: pos.bottom,
                      width: pos.width,
                      maxHeight: pos.maxHeight,
                    }}
                  >
                    <p className="dp-eyebrow px-2 pb-1.5">Suggested prompts</p>
                    <div className="space-y-0.5">
                      {suggestions.map((question) => (
                        <button
                          key={question}
                          type="button"
                          onClick={() => fill(question)}
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
                )
              : null}
          </div>
        )}

        <textarea
          ref={inputRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            const desktop =
              typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;
            if (desktop && event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (canSend) onSubmit?.();
            }
          }}
          rows={1}
          placeholder={placeholder}
          className={`dp-composer-input ${compact ? "h-8 text-[11px]" : "h-9 text-[12.5px]"}`}
        />

        {busy ? (
          <button
            type="button"
            onClick={() => onStop?.()}
            aria-label="Stop generating"
            className={`dp-send dp-stop ${compact ? "h-8 w-8" : ""}`}
          >
            <Icon name="stop" size={compact ? 11 : 13} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            className={`dp-send ${compact ? "h-8 w-8" : ""} ${!canSend ? "is-disabled" : ""}`}
          >
            <Icon name="arrowUp" size={compact ? 14 : 16} strokeWidth={2} />
          </button>
        )}
      </div>

      {!compact && (
        <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[9px] text-subtle">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="shield" size={10} />
            Grounded in factory data
          </span>
          <span className="hidden items-center gap-1.5 sm:inline-flex">
            <span className="dp-kbd">Enter</span> to send
          </span>
        </div>
      )}
    </form>
  );
}
