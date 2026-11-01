import { cx } from "./cx.js";

export function Spinner({ size = 16, className, label }) {
  return (
    <span
      className={cx("inline-flex items-center justify-center text-current", className)}
      role={label ? "status" : undefined}
      aria-label={label || undefined}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        className="animate-spin"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
        <path
          d="M21 12a9 9 0 0 0-9-9"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

/** Centered spinner + label, useful for panels and page sections. */
export function LoadingState({ label = "Loading…", className }) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center gap-3 py-12 text-center",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Spinner size={22} className="text-accentText" />
      <p className="type-sm text-muted">{label}</p>
    </div>
  );
}
