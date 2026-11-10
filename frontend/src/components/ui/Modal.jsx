import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { cx } from "./cx.js";
import IconButton from "./IconButton.jsx";

const WIDTH = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/**
 * Accessible modal dialog rendered in a portal. Closes on Escape / backdrop
 * click, locks body scroll and moves focus into the panel on open.
 */
export default function Modal({
  open,
  onClose,
  title,
  description,
  footer,
  size = "md",
  className,
  children,
}) {
  const panelRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose?.();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => panelRef.current?.focus());
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      window.cancelAnimationFrame(frame);
    };
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div
        className="absolute inset-0 bg-black/45"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={cx(
          "relative w-full max-h-[92dvh] overflow-y-auto overscroll-contain rounded-t-xl border border-line bg-surface text-foreground shadow-float outline-none sm:rounded-card",
          WIDTH[size] || WIDTH.md,
          className,
        )}
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            {title && (
              <h2 id={titleId} className="type-h3 text-foreground">
                {title}
              </h2>
            )}
            {description && (
              <p id={descriptionId} className="mt-1 type-sm text-muted">
                {description}
              </p>
            )}
          </div>
          {onClose && (
            <IconButton size="sm" aria-label="Close dialog" onClick={onClose}>
              <CloseIcon />
            </IconButton>
          )}
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-4">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
