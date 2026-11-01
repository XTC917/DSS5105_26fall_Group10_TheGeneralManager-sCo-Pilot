import { forwardRef } from "react";
import { cx } from "./cx.js";

const VARIANT = {
  ghost: "text-muted hover:bg-surfaceMuted hover:text-foreground",
  secondary:
    "bg-surface text-foreground border border-line shadow-xs hover:bg-surfaceMuted",
  accent: "bg-accent text-accentContrast shadow-xs hover:brightness-110",
};

const SIZE = {
  sm: "h-8 w-8 rounded-md",
  md: "h-10 w-10 rounded-control",
  lg: "h-12 w-12 rounded-lg",
};

/**
 * Square icon-only button. An `aria-label` (or `title`) is required for a11y.
 */
const IconButton = forwardRef(function IconButton(
  { variant = "ghost", size = "md", className, children, "aria-label": ariaLabel, title, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      title={title || ariaLabel}
      aria-label={ariaLabel}
      className={cx(
        "focus-ring inline-flex items-center justify-center transition-colors duration-[var(--dur-fast)] disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT[variant] || VARIANT.ghost,
        SIZE[size] || SIZE.md,
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
});

export default IconButton;
