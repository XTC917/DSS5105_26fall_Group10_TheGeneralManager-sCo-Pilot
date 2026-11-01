import { cx } from "./cx.js";

const VARIANT = {
  neutral: "bg-surfaceMuted text-muted border border-line",
  accent: "bg-accentSoft text-accentText border border-transparent",
  success: "bg-successSoft text-success border border-transparent",
  warning: "bg-warningSoft text-warning border border-transparent",
  danger: "bg-dangerSoft text-danger border border-transparent",
  solid: "bg-accent text-accentContrast border border-transparent",
};

const SIZE = {
  sm: "h-5 px-2 type-caption",
  md: "h-6 px-2.5 type-caption",
};

/** Compact status / label pill. */
export default function Badge({
  variant = "neutral",
  size = "md",
  dot = false,
  className,
  children,
  ...props
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full font-medium leading-none",
        VARIANT[variant] || VARIANT.neutral,
        SIZE[size] || SIZE.md,
        className,
      )}
      {...props}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
