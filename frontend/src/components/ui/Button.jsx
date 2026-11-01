import { forwardRef } from "react";
import { cx } from "./cx.js";
import { Spinner } from "./Spinner.jsx";

const VARIANT = {
  primary:
    "bg-accent text-accentContrast shadow-xs hover:brightness-110 active:brightness-95",
  secondary:
    "bg-surface text-foreground border border-line shadow-xs hover:bg-surfaceMuted active:bg-surfaceMuted",
  subtle: "bg-accentSoft text-accentText hover:brightness-95 active:brightness-90",
  ghost: "bg-transparent text-foreground hover:bg-surfaceMuted active:bg-surfaceMuted",
  danger: "bg-danger text-white shadow-xs hover:brightness-110 active:brightness-95",
};

const SIZE = {
  sm: "h-8 gap-1.5 px-3 text-xs",
  md: "h-10 gap-2 px-4 text-sm",
  lg: "h-12 gap-2 px-6 text-base",
};

/**
 * Primary action button. Variants map to semantic accent tokens so the whole
 * app can be re-themed by switching data-accent / data-theme.
 */
const Button = forwardRef(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    disabled = false,
    fullWidth = false,
    leadingIcon = null,
    trailingIcon = null,
    className,
    children,
    type = "button",
    ...props
  },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cx(
        "focus-ring inline-flex select-none items-center justify-center whitespace-nowrap rounded-control font-medium transition-[filter,background-color,color,box-shadow] duration-[var(--dur-fast)] disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT[variant] || VARIANT.primary,
        SIZE[size] || SIZE.md,
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size={size === "sm" ? 13 : 15} /> : leadingIcon}
      {children != null && <span>{children}</span>}
      {!loading && trailingIcon}
    </button>
  );
});

export default Button;
